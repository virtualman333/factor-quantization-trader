# AGENTS.md — AI 协作开发指南

本文档面向 AI 编程助手和项目贡献者，描述项目架构、设计决策、数据流和开发规范。

---

## 🎯 项目定位

因子量化交易系统是一个面向 OKX 交易所的全栈量化交易平台，核心目标：

1. 从 OKX 拉取行情数据并本地持久化
2. 基于多因子模型生成交易信号
3. 自动或手动执行交易，包含完整风控
4. 支持模拟盘/实盘双环境，数据隔离

---

## 🏗️ 架构设计

### 分层架构

```
┌──────────────────────────────────────────┐
│  Presentation Layer (Vue 3 + Element Plus)│
│  views/ ← 页面组件                        │
│  stores/ ← Pinia 状态 (connection)        │
│  api/ ← Axios 封装                        │
└────────────────┬─────────────────────────┘
                 │ HTTP REST
┌────────────────▼─────────────────────────┐
│  API Layer (DRF ViewSets + @action)       │
│  apps/*/views.py ← 视图 + 分页 + 过滤     │
│  apps/*/serializers.py ← 数据序列化       │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│  Service Layer (业务逻辑)                  │
│  apps/*/services.py ← 核心业务            │
│  core/risk_manager.py ← 风控              │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│  Data Access Layer (Django ORM + 外部API) │
│  apps/*/models.py ← 数据模型              │
│  core/okx_client.py ← OKX SDK 封装        │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│  Infrastructure                           │
│  MySQL / Redis / Celery / Celery Beat     │
└──────────────────────────────────────────┘
```

### 核心设计原则

1. **服务层 (services.py) 承载业务逻辑**，ViewSet 只做参数校验和响应
2. **OKX 客户端单例** (`core/okx_client.py`)，按 `SystemConfig.active_environment` 切换凭证
3. **K 线数据按环境隔离** (`environment` 字段)，模拟盘/实盘互不影响
4. **前端通过 `useConnectionStore` 管理环境状态**，顶部导航栏可随时切换

---

## 📦 应用模块

### `apps/market/` — 行情数据

| 文件 | 职责 |
|------|------|
| `models.py` | `Instrument`(品种), `KLine`(K线, 含 `environment`), `Ticker`(快照), `FundingRate`(资金费率) |
| `services.py` | `MarketDataService`: 从 OKX 拉取数据并入库，`_get_current_env()` 获取当前环境 |
| `views.py` | `KLineViewSet`: 含 `scroll` 游标加载接口（支持左右滑动懒加载）和 `fetch` 手动拉取 |
| `tasks.py` | Celery 定时同步任务 |

**K 线加载流程**:
```
用户打开 K 线页面 → chart.setLoadDataCallback → GET /klines/scroll/
  → 查数据库 (按 environment 过滤)
  → 不足时 auto_fetch: 从 OKX 拉取 → 入库 (带 environment)
  → 返回 {results, has_more, environment}
```

### `apps/account/` — 账户管理

| 文件 | 职责 |
|------|------|
| `models.py` | `OKXCredential`(demo/live 双凭证), `SystemConfig`(单例, 存 active_environment), `BalanceSnapshot`, `PositionSnapshot`, `NetValueHistory` |
| `views.py` | `OKXCredentialViewSet`: 凭证 CRUD + `switch_env` + `test_connection` |
| `services.py` | 余额/持仓/净值快照同步 |

**环境切换流程**:
```
前端 → POST /account/credentials/switch_env/ {environment: "live"}
  → SystemConfig.active_environment = "live"
  → 重置 OKX 客户端 (_okx_client = None)
  → 下次调用 get_okx_client() 时重新加载 live 凭证
  → 前端 Klines.vue watch 到 environment 变化 → 重建图表
```

### `apps/strategy/` — 策略引擎

| 文件 | 职责 |
|------|------|
| `models.py` | `StrategyConfig`(3 种策略类型), `FactorDefinition`(因子定义), `SignalRecord`(信号), `TrackedPosition`(持仓跟踪), `BacktestResult`(回测) |
| `services.py` | `StrategyEngine`: 因子计算 (`ta` 库) → 综合评分 → 信号生成 → 回测执行 → 策略运行 |
| `views.py` | 策略/因子/信号/回测 CRUD + `run` 和 `backtest` action |
| `tasks.py` | Celery Beat 定时执行活跃策略 |

**因子计算流程**:
```
StrategyEngine._compute_factors(kline_df)
  → momentum (ROC), volatility (ATR/BBW)
  → rsi, macd, bbands, volume_ratio, trend_strength (ADX)
  → _normalize_factors() → 0~1 标准化
  → _composite_score() → 加权综合评分
  → _generate_signals() → buy/sell/hold
```

### `apps/orders/` — 订单管理

| 文件 | 职责 |
|------|------|
| `models.py` | `TradeOrder`(订单), `OrderLog`(操作日志) |
| `views.py` | `TradeOrderViewSet`: 下单/撤单/改单/状态查询 |
| `services.py` | `OrderService`: 调用 OKX SDK 下单，写风控检查 |

### `core/` — 公共模块

| 文件 | 职责 |
|------|------|
| `okx_client.py` | OKX REST API 封装，懒加载子模块 (Market/Account/Trade)，`_safe_call` 统一异常处理 |
| `ws_client.py` | OKX WebSocket 客户端，支持公共频道 (K线/行情) 和私有频道 (账户/订单) |
| `risk_manager.py` | `RiskManager`: 下单前 7 项风控检查 + 止损计算 |
| `exceptions.py` | 异常体系: `QuantTradingError` → `OKXClientError`, `RiskLimitExceeded`, `StrategyError` 等 |

---

## 🔑 关键设计决策

### 1. 模拟盘/实盘隔离

- **不创建两套数据库**，而是在关键表加 `environment` 字段
- 当前 `KLine` 已隔离，`BalanceSnapshot`/`PositionSnapshot` 等通过 OKX SDK 的 `flag` 参数区分（不同的 API 端点返回不同数据）
- `SystemConfig` 单例表控制全局环境

### 2. K 线数据懒加载

- 使用 klinecharts 的 `setLoadDataCallback`，按时间游标分页
- `scroll` 接口支持 `before`/`after` 参数
- `auto_fetch` 机制：数据库不足时自动从 OKX 拉取回填

### 3. 风控在订单层执行

- `RiskManager.pre_order_check()` 在下单前执行 7 项检查
- 每日统计通过 Redis 缓存持久化（跨进程共享）
- 止损检查在策略运行循环中执行

### 4. Celery 定时策略执行

- Beat 每分钟触发 `run_active_strategies` 和 `execute_pending_signals`
- Worker 异步执行，不阻塞 HTTP 请求
- 策略状态变更通过数据库持久化

---

## 📝 开发规范

### 代码风格

- **Python**: PEP 8，4 空格缩进，类型标注（可选）
- **Vue**: Composition API (`<script setup>`)，单文件组件
- **命名**: 蛇形命名 (Python) / 驼峰命名 (JS/Vue)

### 添加新 API 端点

1. 在对应 app 的 `models.py` 定义模型（如需要）
2. 在 `services.py` 编写业务逻辑
3. 在 `views.py` 的 ViewSet 中添加 `@action` 或新方法
4. 在 `frontend/src/api/` 添加对应的 Axios 调用函数

### 添加新的技术因子

1. 在 `apps/strategy/services.py` 的 `_compute_factors()` 中添加计算逻辑
2. 在 `_normalize_factors()` 中添加标准化处理
3. 在 `scripts/init_factors.py` 中添加 `FactorDefinition` 初始化
4. 在策略表单的因子选择列表中展示

### 添加新的策略类型

1. 在 `StrategyConfig.STRATEGY_TYPE_CHOICES` 中添加选项
2. 在 `StrategyEngine` 中实现对应的信号生成逻辑
3. 在回测逻辑中支持该策略类型

### 数据库变更

```bash
# 修改 models.py 后
python manage.py makemigrations
python manage.py migrate
```

迁移文件命名格式: `{序号}_{描述}.py`

### 前端页面规范

- 页面组件放在 `views/{模块}/` 下
- API 调用放在 `api/{模块}.js` 下
- 全局状态放 `stores/` (Pinia)
- 路由在 `router/index.js` 注册，`meta.title` 和 `meta.icon` 必填

---

## 🧪 测试

```bash
# 运行策略冒烟测试
python scripts/test_volume_strategy.py

# 命令行运行策略
python manage.py shell < scripts/run_strategy.py

# 拉取 K 线测试
python manage.py fetch_klines --inst_id BTC-USDT --bar 1H --limit 200
```

---

## 🚢 部署注意事项

1. **生产环境必须修改**:
   - `DJANGO_SECRET_KEY` — 使用强随机密钥
   - `DJANGO_DEBUG=False`
   - `CORS_ALLOW_ALL_ORIGINS=False`，配置具体域名
   - `DEFAULT_PERMISSION_CLASSES` 改为 `IsAuthenticated`

2. **前端构建**:
   ```bash
   cd frontend && npm run build
   ```
   产出在 `frontend/dist/`，由 Nginx 或 Django 静态文件服务托管

3. **Celery 生产化**:
   ```bash
   celery -A config worker -l info --concurrency=4
   celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```

---

## 📚 相关文档

- [README.md](./README.md) — 项目概述和快速开始
- [CONTRIBUTING.md](./CONTRIBUTING.md) — 贡献指南
- [OKX API 文档](https://www.okx.com/docs-v5/)
- [KLineCharts 文档](https://www.klinecharts.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Element Plus](https://element-plus.org/)
