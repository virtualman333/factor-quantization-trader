# 待开发列表 (Roadmap)

> 状态标记：🔴 高优先级  🟡 中优先级  🟢 低优先级  ✅ 已完成


## 🔴 P0 — 多用户支持

> 当前系统为单用户设计（全局 SystemConfig、全局 OKX 客户端单例），
> 需要改造为多用户架构，每个用户独立管理自己的策略和凭证。
- [x] **管理员功能**
  - [x] 系统级配置（全局风控参数、市场数据同步）
  - [x] 用户使用统计面板
  - [x] 用户配额管理（API 调用频率、策略数量上限）

---

## 🟡 P1 — 实时数据

- [x] **WebSocket 实时推送**
  - [x] 后端：Django Channels / SSE 将 OKX WebSocket 数据推送到前端
  - [x] 前端：Tickers 页面实时价格更新（替代当前 HTTP 轮询）
  - [x] 前端：K 线页面实时更新最新 K 线
  - [x] 前端：仪表盘实时数据卡片
  - [x] 连接状态指示器实时反映 WS 状态

- [ ] **实时通知**
  - [ ] 策略信号通知（弹窗/消息提示）
  - [ ] 订单成交通知
  - [ ] 止损/止盈触发通知
  - [ ] 风控告警通知

---

## 🟡 P1 — 运维基础设施

- [x] **Docker 容器化**
  - [x] `Dockerfile`（Python 后端 + gunicorn）
  - [x] `Dockerfile.celery`（Celery Worker）
  - [x] `Dockerfile.celery-beat`（Celery Beat）
  - [x] `Dockerfile.frontend`（Node 编译 + Nginx 托管）
  - [x] `docker-compose.yml`（MySQL 8.0 + Redis 7 + Django + Celery + Nginx，含健康检查）
  - [x] `.dockerignore`
  - [x] Nginx 反向代理配置 + MySQL 初始化脚本

- [x] **日志系统**
  - [x] `LOGGING` 配置（控制台 + 文件 + TimedRotatingFileHandler 按日期轮转）
  - [x] 请求日志中间件 `RequestLogMiddleware`（方法/路径/状态码/耗时/用户/IP，按状态分级）
  - [x] Celery 任务日志独立文件（celery.log / celery_error.log）
  - [x] 错误日志分级（error.log 90天 / warning.log 60天 / app.log 30天）
  - [x] 静态资源请求日志过滤 `SkipStaticRequestsFilter`
  - [x] Sentry 集成预留（生产环境可选开启）

- [x] **环境管理**
  - [x] `production.py` 生产环境配置（HTTPS/HSTS/DB连接池/CORS/限流/Celery资源限制/Email通知）
  - [x] 环境变量区分 dev/staging/prod（`.env.dev` / `.env.staging` / `.env.prod`）
  - [x] Secret 管理（`ENV_FILE` 按环境加载，.gitignore 排除所有 `.env.*` 实际密钥）
  - [x] `DJANGO_ENVIRONMENT` 变量标识当前运行环境
  - [x] `gunicorn` + `sentry-sdk` 加入依赖

---

## 🟡 P1 — API 文档 & 可观测性

- [ ] **Swagger / OpenAPI 文档**
  - [ ] 引入 `drf-spectacular`
  - [ ] 自动生成 OpenAPI Schema
  - [ ] Swagger UI（`/api/docs/`）+ ReDoc（`/api/redoc/`）
  - [ ] ViewSet 和 Serializer 添加文档注解

- [x] **性能监控**
  - [x] Django Debug Toolbar（开发环境）
  - [x] Silk 请求性能分析
  - [x] Celery 任务监控（Flower）
  - [x] 数据库慢查询日志
  - [x] Redis 内存使用监控

---

## 🟢 P2 — 功能增强

- [x] **策略引擎增强**
  - [x] 策略参数优化器（网格搜索/贝叶斯优化）
  - [x] 更多因子：OBV、CCI、威廉指标、一目均衡表
  - [x] 因子权重自动优化（基于回测结果）
  - [x] 多策略组合管理（策略组合 + 资金分配）
  - [x] 策略对比分析（多策略回测结果对比图表）
  - [x] 自定义因子支持（用户可配置计算逻辑）

- [ ] **回测增强**
  - [ ] 回测报告导出（PDF/HTML）
  - [ ] 蒙特卡洛模拟
  - [ ] 滑点/手续费模拟
  - [ ] 多品种并行回测
  - [ ] Walk-forward 分析

- [ ] **K 线图表增强**
  - [ ] 更多技术指标切换：BOLL、KDJ、EMA、WR
  - [ ] 深色/浅色主题切换
  - [ ] 画线工具（趋势线、水平线、斐波那契）
  - [ ] 多时间周期联动（同屏显示多个周期）
  - [ ] 品种对比叠加

- [ ] **仪表盘增强**
  - [ ] 策略收益排行图表
  - [ ] 因子热力图
  - [ ] 市场概览面板（涨跌幅排行）
  - [ ] 净值实时曲线图（WebSocket 推送）

- [ ] **订单管理增强**
  - [ ] 批量下单
  - [ ] 条件单（止盈止损单）
  - [ ] 冰山/TWAP 算法订单
  - [ ] 订单模板/快捷下单

- [ ] **账户管理增强**
  - [ ] 多账户管理（多 OKX 账户绑定）
  - [ ] 盈亏分析报表（日/周/月）
  - [ ] 手续费统计
  - [ ] 资金曲线与基准对比（BTC 走势对比）

---

## 🟢 P2 — 前端体验优化

- [ ] **状态管理完善**
  - [ ] 策略 Store（Pinia），避免重复 API 请求
  - [ ] 行情 Store，缓存 Ticker 数据
  - [ ] 订单 Store，实时更新订单状态

- [ ] **UX 优化**
  - [ ] 全局 Loading 骨架屏
  - [ ] 操作确认弹窗（删除策略、撤单、切换实盘）
  - [ ] 表单持久化（浏览器关闭后恢复未提交内容）
  - [ ] 快捷键支持
  - [ ] 深色模式

- [ ] **移动端适配**
  - [ ] 响应式布局优化
  - [ ] 移动端专用 K 线页面（触摸手势）
  - [ ] PWA 支持

---

## 🟢 P2 — 数据处理

- [ ] **数据管理**
  - [ ] K 线数据自动清理策略（过期数据归档/删除）
  - [ ] 数据导出功能（CSV/Excel）
  - [ ] 数据导入功能（外部数据源）
  - [ ] 数据库备份脚本

- [ ] **数据分析**
  - [ ] 相关性分析矩阵
  - [ ] 因子有效性统计（IC/IR 分析）
  - [ ] 市场状态分类（趋势/震荡/高波动）

---

## 🟢 P3 — 高级特性

- [ ] **AI/ML 集成**
  - [ ] LSTM/Transformer 价格预测
  - [ ] 强化学习交易智能体
  - [ ] NLP 市场情绪分析（新闻/社交媒体）
  - [ ] 因子自动发现（遗传算法/符号回归）

- [ ] **多交易所支持**
  - [ ] Binance API 适配
  - [ ] Bybit API 适配
  - [ ] 统一行情/交易抽象层
  - [ ] 跨交易所套利

- [ ] **社区功能**
  - [ ] 策略分享/市场
  - [ ] 策略跟单
  - [ ] 排行榜

---

## 📊 进度总览

| 分类 | 总数 | 已完成 | 进度 |
|------|------|--------|------|
| P0 安全与认证 | 10 | 10 | 100% |
| P0 多用户支持 | 28 | 28 | 100% |
| P1 实时数据 | 9 | 5 | 56% |
| P1 运维基础设施 | 16 | 16 | 100% |
| P1 API 文档 & 可观测性 | 8 | 0 | 0% |
| P2 功能增强 | 37 | 0 | 0% |
| P2 前端体验 | 12 | 0 | 0% |
| P2 数据处理 | 6 | 0 | 0% |
| P3 高级特性 | 10 | 0 | 0% |
| **合计** | **136** | **45** | **33%** |

---

## 🎯 建议的迭代计划

### Sprint 1（多用户 & 安全，预计 2-3 周）
1. 数据模型添加 `user` 外键 + 数据库迁移
2. JWT 认证 + 登录/注册页面
3. API 层按用户过滤 + 权限控制
4. 前端路由守卫 + Auth Store
5. 统一错误响应格式

### Sprint 2（运维 & 实时，预计 1-2 周）
1. ~~Docker 容器化~~ ✅
2. ~~日志系统配置~~ ✅
3. K 线/Ticker 实时 WebSocket 推送

### Sprint 3（实时 & 监控，预计 1-2 周）
1. K 线/Ticker 实时 WebSocket 推送
2. Swagger API 文档
3. Django Debug Toolbar + Silk
4. Celery Flower 监控

### Sprint 4+（功能迭代）
按 P2 → P3 优先级持续迭代
