# 金叉银叉策略新增 + 现有策略优化

## Context（背景）

用户要求新增一个金叉银叉策略，并优化现有3个策略（trend_follow / volume_breakout / factor_composite）。

探索发现的关键问题：
1. **现有 trend_follow**（EMA12/26 金叉死叉）缺止损止盈价输出、无量能确认、score 计算粗糙
2. **volume_breakout** 的 `daily_max_stop` 参数定义了但 `generate_signal` 中从未使用；无 ADX 趋势强度过滤
3. **factor_composite** 缺止损止盈价输出和平仓逻辑
4. **services.py 止损监控被硬编码限制**为 `strategy_type == 'volume_breakout'`（L173/L232/L272/L390），导致其他策略即使输出止损止盈价，实盘也不会执行止损止盈

用户已确认：
- 金叉银叉策略采用**多级别共振**方案（快/中/慢三档 EMA + MACD + 量能确认）
- 优化范围：**全部3个策略**

预期结果：新增一个与 trend_follow 差异化的金叉银叉策略；3个现有策略补齐止损止盈/风控能力；services.py 止损监控泛化，让所有策略的止损止盈价在实盘生效。

---

## 一、新增金叉银叉策略

### 文件：`apps/strategy/strategies/golden_cross.py`（新建）

**与 trend_follow 的差异化**：trend_follow 是单档 EMA(12/26) + ADX；golden_cross 是三档 EMA(快/中/慢) + MACD 共振 + 量能确认 + 六维加权评分。

**PARAM_SCHEMA**（约18个参数）：
- 三档 EMA：`ema_fast`(5) / `ema_mid`(20) / `ema_slow`(60)
- MACD：`macd_fast`(12) / `macd_slow`(26) / `macd_signal`(9)
- 量能：`vol_ma_len`(20) / `vol_ratio`(1.5)
- 评分阈值：`min_score`(0.60 开仓) / `exit_score`(0.45 平仓)
- ATR 止损止盈：`atr_len`(14) / `stop_loss_mul`(1.5) / `tp_mode`(fixed|trailing) / `tp_ratio`(2.0) / `trailing_trigger`(0.8) / `trailing_factor`(0.6)
- 风控：`cooling_min`(5) / `daily_max_stop`(3)

**MIN_BARS = 120**（慢线60 + MACD 26+9 + 安全余量）

**generate_signal 核心逻辑**：
1. 计算三档 EMA + MACD(线/信号/柱) + 量能均线 + ATR
2. 检测穿越（取最后两根）：
   - 银叉 = 快线穿中线；金叉 = 快线穿慢线；中线穿慢线 = 趋势确认；MACD 金叉/死叉
3. **共振评分**（穿越满分1.0，同向排列半分0.5，反向0）：
   - 权重：金叉0.30 > 银叉0.20 > 中线穿慢线0.15 = MACD 0.15 > 量能0.10 = 价格位置0.10
   - 量能：放量(vol≥均量×vol_ratio)满分，温和放量(vol≥均量)半分
   - 价格位置：价在慢线上方/下方
4. **平仓**：持多时 bear_score≥exit_score → close_long；持空时 bull_score≥exit_score → close_short
5. **开仓**：bull_score≥min_score 且 价在慢线上方 且 冷却OK 且 日止损OK → buy（输出 ATR 止损止盈价）；空头镜像
6. NaN 防御：关键指标 NaN 时返回 hold

**辅助方法**（复制自 volume_breakout，保持一致）：
- `_calculate_atr(df, atr_len)` 静态方法
- `_cooling_ok(symbol, signal_type, cooling_min, context)` 查 SignalRecord 最近同向信号
- `_daily_stop_ok(symbol, context)` 查 TrackedPosition.daily_stop_count（回测 check_cooling=False 跳过；daily_max_stop=0 不限制；跨日重置）

---

## 二、优化 trend_follow.py

### 改动点（向后兼容，现有4参数默认值不变）

1. **PARAM_SCHEMA 追加**（在 `adx_threshold` 之后）：
   - `atr_len`(14) / `stop_loss_mul`(1.5) / `tp_mode`(fixed) / `tp_ratio`(2.0)
   - `vol_confirm`(bool, False 开关) / `vol_ma_len`(20)
   - `cooling_min`(5) / `daily_max_stop`(3)

2. **score 精细化**（替换 `min(adx/50,1) if adx>20 else 0.3`）：
   - `adx_score = clip((adx - adx_threshold) / (50 - adx_threshold), 0, 1)`
   - `cross_bonus = 1.0 if 金叉/死叉 else 0.5`（穿越满分，排列半分）
   - `score = 0.6*adx_score + 0.4*cross_bonus`

3. **ATR 止损止盈价输出**（开仓 buy/sell 时计算，复用 `_calculate_atr`）

4. **量能确认开关**（`vol_confirm=True` 时要求当前量≥均量×1.2 才开仓）

5. **冷却 + 日止损检查**（复制 `_cooling_ok` / `_daily_stop_ok` 方法，开仓前检查）

6. **平仓逻辑不变**（死叉/跌破均线即平，平仓不受冷却限制）

---

## 三、优化 volume_breakout.py

### 改动点（向后兼容）

1. **`daily_max_stop` 实际生效**：
   - 新增 `_daily_stop_ok(symbol, context)` 方法（与 golden_cross 相同实现）
   - 开仓条件追加 `and daily_stop_ok`（L145、L150）
   - detail 增加 `daily_stop_ok` 字段

2. **ADX 趋势强度过滤（可选开关）**：
   - PARAM_SCHEMA 追加：`adx_filter`(bool, False) / `adx_period`(14) / `adx_threshold`(20)
   - `adx_filter=True` 时计算 ADX，要求 ADX≥阈值才开仓
   - 开仓条件追加 `and adx_ok`（仅开关开启时可能为 False）

---

## 四、优化 factor_composite.py

### 改动点（向后兼容，buy_threshold/sell_threshold 默认值不变）

1. **PARAM_SCHEMA 追加**：
   - `atr_len`(14) / `stop_loss_mul`(1.5) / `tp_mode`(fixed) / `tp_ratio`(2.0)
   - `exit_threshold`(0.45 平仓评分阈值)
   - `cooling_min`(5) / `daily_max_stop`(3)

2. **新增平仓逻辑**（持仓中）：
   - 持多且 composite_score≤exit_threshold → close_long
   - 持空且 composite_score≥(1-exit_threshold) → close_short

3. **止损止盈价输出**（开仓时基于综合评分方向 + ATR 计算）

4. **冷却 + 日止损检查**（复制 `_cooling_ok` / `_daily_stop_ok`）

5. **`StrategySignal` 构造补齐** stop_loss_price / take_profit_price / entry_atr / tp_mode

---

## 五、泛化 services.py 止损监控（让优化生效）

### 改动点（`apps/strategy/services.py`）

1. **L232 `_sync_tracked_position_after_exec`**：
   - 旧：`if strategy.strategy_type != 'volume_breakout': return`
   - 新：`if not signal.stop_loss_price and signal.signal in ('buy', 'sell'): return`（无止损价的开仓信号不跟踪；平仓信号仍需更新持仓状态）

2. **L272 `monitor_positions_for_strategy`**：
   - 旧：`if strategy.strategy_type != 'volume_breakout': return`
   - 新：`if not TrackedPosition.objects.filter(strategy=strategy, is_open=True).exists(): return`（有开放持仓才监控）

3. **L390 `monitor_all_active_strategies`**：
   - 旧：`filter(status='active', strategy_type='volume_breakout')`
   - 新：`filter(status='active')`（监控所有活跃策略）

4. **L173 `execute_signal` 仓位计算**（推荐）：
   - 旧：`if strategy.strategy_type == 'volume_breakout' and ... and signal.stop_loss_price is not None:`
   - 新：`if signal.signal in ('buy', 'sell') and signal.stop_loss_price is not None:`（任何有止损价的开仓信号用风险公式，`risk_per_trade` 走 `impl.param('risk_per_trade', 0.01)` 默认值）
   - **影响**：trend_follow/factor_composite/golden_cross 开仓仓位从按 order_size_pct 改为风险公式（基于止损距离）。这是合理优化，但改变了仓位行为。

> 说明：第4项会改变非 volume_breakout 策略的仓位计算方式。若希望保守，可只做1-3项（止损监控泛化），仓位计算保持现状。推荐做第4项以让风控完整。

---

## 六、注册新策略

### 文件：`apps/strategy/strategies/__init__.py`

按字母序插入 `import apps.strategy.strategies.golden_cross  # noqa: F401`（在 factor_composite 之后、trend_follow 之前）。

---

## 七、测试脚本

### 文件：`scripts/test_golden_cross_strategy.py`（新建，参考 `test_volume_strategy.py` 范式）

**DataFrame 构造** `make_golden_cross_df(n=150, scenario)`：
- `'bull'`：前80根缓跌（空头排列）+ 后70根急涨（触发金叉共振）+ 末根放量
- `'bear'`：前80根缓涨（多头排列）+ 后70根急跌（触发死叉共振）+ 末根放量
- `'flat'`：窄幅震荡，无共振

**4个测试场景**：
1. 金叉共振 → buy（断言 stop_loss_price<price, take_profit_price>price, entry_atr>0）
2. 死叉共振 → sell（断言止损止盈方向正确）
3. 持多 + 死叉共振 → close_long
4. 震荡 → hold/无信号（断言不产生 buy/sell）

**调用方式**：mock OKX + `StrategyService.generate_signals(strategy)`（统一入口，非旧的 `_generate_volume_breakout_signals`）。

---

## 八、关键文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `apps/strategy/strategies/golden_cross.py` | 新建 | 金叉银叉策略主体 |
| `apps/strategy/strategies/trend_follow.py` | 修改 | 补 ATR止损/score精细化/量能开关/冷却 |
| `apps/strategy/strategies/volume_breakout.py` | 修改 | daily_max_stop生效 + ADX过滤开关 |
| `apps/strategy/strategies/factor_composite.py` | 修改 | 补止损止盈/平仓逻辑/冷却 |
| `apps/strategy/strategies/__init__.py` | 修改 | 注册 golden_cross |
| `apps/strategy/services.py` | 修改 | 泛化止损监控（L173/232/272/390） |
| `scripts/test_golden_cross_strategy.py` | 新建 | 冒烟测试 |

**复用的现有资源**：
- `BaseStrategy` / `ParamSchema` / `StrategySignal`（`apps/strategy/base.py`）
- `@register` 装饰器（`apps/strategy/registry.py`）
- `VolumeBreakoutStrategy._calculate_atr` / `_cooling_ok` 实现模式（复制到新策略）
- `TrackedPosition.daily_stop_count` / `daily_stop_date` 字段（`apps/strategy/models.py` L220-221，已由 monitor 在止损时递增）

---

## 九、验证步骤

```bash
# 1. 运行金叉银叉策略冒烟测试（4个场景）
python scripts/test_golden_cross_strategy.py

# 2. 运行现有放量跟随测试（确保优化未破坏）
python scripts/test_volume_strategy.py

# 3. 验证策略注册
python manage.py shell -c "
from apps.strategy.registry import registry
registry.auto_discover()
print('已注册策略:', registry.codes())
# 应包含 'golden_cross'
"

# 4. 启动 Django，访问 meta 接口
python manage.py runserver
# GET /api/strategy/configs/meta/ 应包含 code='golden_cross'，params 含完整 schema

# 5. 前端验证（cd frontend && npm run dev）
#    - 新建策略 → 策略类型下拉出现"金叉银叉"
#    - 选中后参数表单按 PARAM_SCHEMA 动态渲染
#    - 编辑现有 trend_follow/volume_breakout/factor_composite，参数表单显示新增字段

# 6. 回测验证
#    POST /api/strategy/configs/{id}/run_backtest/
#    golden_cross 策略回测能跑完并输出交易明细
```

---

## 十、实施顺序

1. 新建 `golden_cross.py` + `__init__.py` 注册 → 验证 meta 接口
2. 写 `test_golden_cross_strategy.py` → 跑通4场景
3. 优化 `volume_breakout.py`（daily_max_stop + ADX 开关）→ 跑 `test_volume_strategy.py` 不破坏
4. 优化 `trend_follow.py`（ATR/score/量能/冷却）
5. 优化 `factor_composite.py`（止损止盈/平仓/冷却）
6. 泛化 `services.py` 止损监控（L232/272/390 必做，L173 推荐）
7. 端到端验证（meta 接口 + 前端下拉 + 回测）

---

## 关键设计决策

1. **共振评分"穿越满分+排列半分"**：避免只有穿越瞬间能开仓，排列状态也能捕捉趋势延续
2. **权重金叉(0.30)>银叉(0.20)**：金叉（快穿慢）是最强信号故权重最高
3. **`daily_max_stop` 按 symbol 粒度**：与 `_cooling_ok` 同构，查 `TrackedPosition`（unique_together=['strategy','inst_id']）
4. **止损止盈价在开仓信号时计算输出**：策略无状态，实盘由 `monitor_positions_for_strategy` 持续检查；回测靠反向共振信号平仓
5. **所有新参数均有默认值**：旧 `StrategyConfig.params` 不含新 key 时走默认值，零破坏
6. **services.py 泛化基于"是否有 stop_loss_price/开放持仓"**：替代 strategy_type 硬编码，让所有输出止损价的策略统一获得实盘止损能力
