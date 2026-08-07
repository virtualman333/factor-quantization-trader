# 📈 因子量化交易系统 (Factor Quantization Trader)

基于 **Django REST Framework + Vue 3** 的全栈量化交易系统，连接 OKX 交易所，支持多因子策略、模拟盘/实盘双环境、自动交易执行。

---

## ✨ 核心功能

| 模块 | 功能 |
|------|------|
| **行情数据** | 交易品种管理、K线数据（专业图表+技术指标）、实时行情、资金费率 |
| **账户管理** | 余额快照、持仓管理、净值曲线、OKX 凭证管理（模拟盘/实盘双环境） |
| **策略引擎** | 因子综合评分、趋势跟踪、放量跟随三种策略，支持回测 |
| **因子体系** | 动量、波动率、RSI、MACD、布林带、成交量、趋势强度等因子 |
| **订单管理** | 手动下单、策略自动下单、订单状态追踪、操作日志 |
| **风控系统** | 仓位限制、每日亏损上限、下单频率控制、止损止盈 |
| **定时任务** | Celery Beat 每分钟运行活跃策略 + 执行待处理信号 |

---

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────┐
│                   前端 (Vue 3)               │
│  Element Plus / ECharts / KLineCharts / Pinia│
│               Vite Dev Server                │
└──────────────────┬──────────────────────────┘
                   │ /api/* 代理
┌──────────────────▼──────────────────────────┐
│            后端 (Django REST Framework)       │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │  market  │ │ account  │ │  strategy   │  │
│  │ 行情数据  │ │ 账户管理  │ │  策略引擎   │  │
│  └──────────┘ └──────────┘ └─────────────┘  │
│  ┌──────────┐ ┌──────────────────────────┐  │
│  │  orders  │ │    core (公共模块)        │  │
│  │ 订单管理  │ │ okx_client / risk_mgr    │  │
│  └──────────┘ └──────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              基础设施                         │
│  MySQL (持久化)  Redis (队列/缓存)            │
│  Celery (异步任务)  Celery Beat (定时调度)     │
└─────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | Django + DRF | 4.2+ |
| 异步任务 | Celery + Redis | 5.3+ |
| 数据库 | MySQL (utf8mb4) | - |
| 前端框架 | Vue 3 + Vite | 3.5+ / 8.1+ |
| UI 组件 | Element Plus | 2.14+ |
| 图表 | ECharts + KLineCharts | 6.1+ / 9.8+ |
| 状态管理 | Pinia | 4.0+ |
| 交易所 SDK | python-okx | 0.4+ |
| 量化计算 | NumPy + Pandas + ta | 1.24+ / 2.0+ / 0.11+ |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 6.0+

### 一键启动（Windows）

```bash
# 双击或运行 start.bat，自动启动全部服务
start.bat
```

脚本会自动完成：环境检查 → 依赖安装 → 数据库迁移 → Celery Worker → Celery Beat → Django 后端 → 前端 Vite。

启动后访问 **http://localhost:5173** 即可使用。关闭窗口自动停止所有服务。

如需手动停止：双击 `stop.bat`。

### 手动启动（Linux/Mac）

```bash
# 1. 克隆 + 配置环境变量
git clone <repo-url>
cd factor-quantization-trader
cp .env.example .env
# 编辑 .env

# 2. 创建虚拟环境 + 安装依赖
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 创建数据库（MySQL）
mysql -u root -p -e "CREATE DATABASE factor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. 数据库迁移 + 初始化
python manage.py migrate
python manage.py shell < scripts/init_factors.py

# 5. 启动所有服务
python manage.py runserver &                    # Django 后端 (8000)
celery -A config worker -l info &               # Celery Worker
celery -A config beat -l info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler &  # Celery Beat
cd frontend && npm install && npm run dev &     # 前端 (5173)
```

或使用 `docker-compose`（见下方 Docker 部署）。

### 配置 OKX 凭证

### 配置 OKX 凭证

1. 打开前端 → **系统设置** → 分别配置「模拟盘」和「实盘」的 API Key
2. 在顶部导航栏下拉菜单中切换交易环境
3. 点击「测试连接」确认凭证可用

---

## 📂 项目结构

```
factor-quantization-trader/
├── manage.py                  # Django 管理入口
├── requirements.txt           # Python 依赖
├── .env.example               # 环境变量模板
├── config/                    # Django 项目配置
│   ├── settings.py            # 全局设置（数据库/Redis/Celery/OKX/风控）
│   ├── urls.py                # 根路由
│   ├── celery.py              # Celery 应用
│   └── wsgi.py / asgi.py      # 部署入口
├── core/                      # 核心公共模块
│   ├── okx_client.py          # OKX REST API 客户端（单例，按环境切换凭证）
│   ├── ws_client.py           # OKX WebSocket 客户端
│   ├── risk_manager.py        # 风控管理器
│   └── exceptions.py          # 异常体系
├── apps/
│   ├── market/                # 行情数据
│   │   ├── models.py          # Instrument / KLine / Ticker / FundingRate
│   │   ├── services.py        # 数据拉取 & 入库
│   │   ├── views.py           # REST API（含 scroll 游标加载）
│   │   ├── serializers.py     # 序列化器
│   │   ├── tasks.py           # Celery 定时任务
│   │   └── admin.py           # Django Admin
│   ├── account/               # 账户管理
│   │   ├── models.py          # OKXCredential / SystemConfig / BalanceSnapshot / NetValueHistory
│   │   ├── views.py           # 余额/持仓/净值/凭证 API
│   │   └── services.py        # 快照服务
│   ├── strategy/              # 策略引擎
│   │   ├── models.py          # StrategyConfig / FactorDefinition / SignalRecord / BacktestResult
│   │   ├── services.py        # 因子计算 / 信号生成 / 回测 / 策略执行
│   │   ├── views.py           # 策略/因子/信号/回测 API
│   │   └── tasks.py           # 定时执行活跃策略
│   └── orders/                # 订单管理
│       ├── models.py          # TradeOrder / OrderLog
│       ├── views.py           # 订单 CRUD API
│       └── services.py        # 下单/撤单/改单服务
├── scripts/                   # 独立脚本
│   ├── init_factors.py        # 初始化因子定义
│   └── run_strategy.py        # 命令行运行策略
└── frontend/                  # Vue 3 前端
    ├── package.json
    ├── vite.config.js         # Vite 配置（代理 /api 到 Django）
    └── src/
        ├── router/index.js    # 14 条路由
        ├── stores/connection.js  # 环境切换 & 连接状态
        ├── api/               # API 调用层
        ├── layout/MainLayout.vue  # 主布局（侧边栏+顶栏）
        └── views/             # 页面组件
            ├── dashboard/     # 仪表盘
            ├── market/        # 行情：品种/K线/行情
            ├── account/       # 账户：余额/持仓/净值
            ├── strategy/      # 策略：配置/因子/信号/回测
            ├── orders/        # 订单：列表/创建
            └── settings/      # 系统设置（凭证配置）
```

---

## 🔌 API 概览

| 路由前缀 | 说明 | 主要端点 |
|----------|------|----------|
| `/api/market/` | 行情数据 | `instruments/` `klines/` `klines/scroll/` `tickers/` `funding-rates/` |
| `/api/account/` | 账户管理 | `balances/` `positions/` `net-value/` `credentials/` `system-config/` |
| `/api/strategy/` | 策略引擎 | `configs/` `factors/` `signals/` `backtests/` |
| `/api/orders/` | 订单管理 | `trades/` |
| `/admin/` | Django Admin | 管理后台 |

### K 线滚动加载

```
GET /api/market/klines/scroll/?inst_id=BTC-USDT&bar=1H&limit=500
GET /api/market/klines/scroll/?inst_id=BTC-USDT&bar=1H&before=1690000000000&limit=500
GET /api/market/klines/scroll/?inst_id=BTC-USDT&bar=1H&after=1690000000000&limit=500
```

- `before`：加载更旧的历史数据（左滑）
- `after`：加载更新的数据（右滑）
- `auto_fetch=true`：数据库数据不足时自动从 OKX 拉取并回填

---

## 🎯 策略类型

### 1. 因子综合评分 (`factor_composite`)

基于多个技术因子（动量、波动率、RSI、MACD、布林带、成交量等）的标准化评分，综合加权后生成买卖信号。

### 2. 趋势跟踪 (`trend_follow`)

基于均线排列、ADX 趋势强度等指标识别趋势方向，顺势交易。

### 3. 放量跟随 (`volume_breakout`)

识别成交量异常放大伴随价格突破的信号，支持固定盈亏比和移动止盈两种出场模式。

---

## 🛡️ 风控体系

| 风控项 | 默认值 | 说明 |
|--------|--------|------|
| 单币种最大仓位 | 20% | 通过 `.env` 中 `MAX_POSITION_PCT` 配置 |
| 单笔最大金额 | 10,000 USD | `MAX_ORDER_VALUE` |
| 每日最大亏损 | 500 USD | `MAX_DAILY_LOSS` |
| 止损比例 | 5% | `STOP_LOSS_PCT` |
| 最小下单间隔 | 1 秒 | 防止高频刷单 |
| 最大同时持仓数 | 5 | 分散风险 |
| 每日最大交易次数 | 50 | 控制交易频率 |

---

## 🔄 模拟盘 / 实盘

系统通过 `SystemConfig.active_environment` 全局切换交易环境：

- **模拟盘 (demo)**：OKX Demo Trading，用于策略测试
- **实盘 (live)**：真实资金交易

K 线数据按 `environment` 字段隔离，切换环境后自动加载对应环境的数据。

---

## 📋 常用命令

```bash
# 数据库
python manage.py migrate              # 运行迁移
python manage.py makemigrations       # 创建迁移

# 初始化数据
python manage.py shell < scripts/init_factors.py   # 初始化因子定义

# 拉取K线
python manage.py fetch_klines --inst_id BTC-USDT --bar 1H --limit 1000

# 运行策略
python manage.py shell < scripts/run_strategy.py

# Celery
celery -A config worker -l info
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# 前端
cd frontend && npm run dev            # 开发模式
cd frontend && npm run build          # 生产构建
```

---

## 🤝 参与贡献

请参阅 [AGENTS.md](./AGENTS.md) 了解项目架构细节，以及 [CONTRIBUTING.md](./CONTRIBUTING.md) 了解贡献流程。

---

## 📄 License

MIT License
