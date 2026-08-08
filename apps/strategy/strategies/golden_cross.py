"""
金叉银叉策略（多级别共振）

与 trend_follow（单档 EMA12/26 + ADX）差异化：三档 EMA（快/中/慢）+ MACD 金叉死叉
+ 量能确认 + 六维加权共振评分。穿越给满分、同向排列给半分，避免仅在穿越瞬间开仓。

信号逻辑：
- 银叉 = 快线穿中线；金叉 = 快线穿慢线；中线穿慢线 = 趋势确认；MACD 金叉/死叉为辅
- 多头共振分 bull_score >= min_score 且价在慢线上方 -> buy
- 空头共振分 bear_score >= min_score 且价在慢线下方 -> sell
- 持仓中反向共振分 >= exit_score -> 平仓
- ATR 计算止损止盈价（固定盈亏比 / 移动止盈）
"""

import logging
from datetime import timedelta

import pandas as pd
import ta

from apps.strategy.base import BaseStrategy, ParamSchema, StrategySignal
from apps.strategy.registry import register

logger = logging.getLogger(__name__)


@register
class GoldenCrossStrategy(BaseStrategy):
    code = 'golden_cross'
    name = '金叉银叉'
    description = '多级别EMA金叉死叉 + MACD共振 + 量能确认，六维加权评分'
    MIN_BARS = 120

    PARAM_SCHEMA = [
        # ---- 三档 EMA 周期 ----
        ParamSchema('ema_fast', '快线周期', 'int', 5, 2, 30, 1,
                    help_text='快速 EMA（银叉触发线，如5/10）'),
        ParamSchema('ema_mid', '中线周期', 'int', 20, 5, 60, 1,
                    help_text='中速 EMA（银叉第二线）'),
        ParamSchema('ema_slow', '慢线周期', 'int', 60, 20, 200, 1,
                    help_text='慢速 EMA（金叉触发线，大趋势锚）'),

        # ---- MACD 参数 ----
        ParamSchema('macd_fast', 'MACD快线', 'int', 12, 5, 30, 1,
                    help_text='MACD 快速 EMA 周期'),
        ParamSchema('macd_slow', 'MACD慢线', 'int', 26, 10, 60, 1,
                    help_text='MACD 慢速 EMA 周期'),
        ParamSchema('macd_signal', 'MACD信号线', 'int', 9, 3, 20, 1,
                    help_text='MACD 信号线周期'),

        # ---- 量能确认 ----
        ParamSchema('vol_ma_len', '量能均线周期', 'int', 20, 5, 100, 1,
                    help_text='成交量均线周期'),
        ParamSchema('vol_ratio', '放量倍数', 'number', 1.5, 1.0, 5.0, 0.1,
                    help_text='当前量 >= 均量 × 该倍数 视为放量（满分）；'
                              '介于1.0~该倍数给0.5分'),

        # ---- 评分阈值 ----
        ParamSchema('min_score', '开仓最低分', 'number', 0.60, 0.30, 0.90, 0.05,
                    help_text='多头/空头共振分 >= 该值才开仓'),
        ParamSchema('exit_score', '平仓触发分', 'number', 0.45, 0.20, 0.70, 0.05,
                    help_text='持仓中反向共振分 >= 该值平仓'),

        # ---- ATR 止损止盈 ----
        ParamSchema('atr_len', 'ATR周期', 'int', 14, 2, 100, 1,
                    help_text='ATR 计算周期'),
        ParamSchema('stop_loss_mul', '止损倍数', 'number', 1.5, 0.1, 5.0, 0.1,
                    help_text='止损距离 = 倍数 × entry_atr'),
        ParamSchema('tp_mode', '止盈模式', 'choice', 'fixed',
                    options=[{'value': 'fixed', 'label': '固定盈亏比'},
                             {'value': 'trailing', 'label': '移动止盈'}],
                    help_text='固定盈亏比 或 移动止盈'),
        ParamSchema('tp_ratio', '固定止盈盈亏比', 'number', 2.0, 0.5, 10.0, 0.1,
                    help_text='固定止盈模式下：盈利 = 盈亏比 × 止损距离'),
        ParamSchema('trailing_trigger', '移动止盈触发倍数', 'number', 0.8, 0.1, 3.0, 0.1,
                    help_text='盈利达 该倍数×止损距离 启动移动止盈'),
        ParamSchema('trailing_factor', '移动追踪幅度', 'number', 0.6, 0.1, 3.0, 0.1,
                    help_text='追踪幅度 = 因子 × entry_atr'),

        # ---- 风控：冷却与日止损 ----
        ParamSchema('cooling_min', '冷却时间(分钟)', 'int', 5, 1, 120, 1,
                    help_text='同方向信号最小间隔'),
        ParamSchema('daily_max_stop', '单日最大止损', 'int', 3, 0, 10, 1,
                    help_text='该标的当日止损达上限后停止开仓（0=不限制）'),
    ]

    # 共振评分权重：金叉最强，其次银叉，中线穿慢线与MACD同权，量能与价格位置同权
    W_SILVER = 0.20  # 银叉（快穿中）
    W_GOLDEN = 0.30  # 金叉（快穿慢）
    W_MID = 0.15     # 中线穿慢线
    W_MACD = 0.15    # MACD 金叉/死叉
    W_VOL = 0.10     # 量能
    W_PRICE = 0.10   # 价格相对慢线位置

    def generate_signal(self, df, symbol, position=None, context=None):
        # 1. 读取参数
        ema_fast_p = int(self.param('ema_fast', 5))
        ema_mid_p = int(self.param('ema_mid', 20))
        ema_slow_p = int(self.param('ema_slow', 60))
        macd_fast = int(self.param('macd_fast', 12))
        macd_slow = int(self.param('macd_slow', 26))
        macd_sig = int(self.param('macd_signal', 9))
        vol_ma_len = int(self.param('vol_ma_len', 20))
        vol_ratio = float(self.param('vol_ratio', 1.5))
        min_score = float(self.param('min_score', 0.60))
        exit_score = float(self.param('exit_score', 0.45))
        atr_len = int(self.param('atr_len', 14))
        stop_loss_mul = float(self.param('stop_loss_mul', 1.5))
        tp_mode = self.param('tp_mode', 'fixed')
        tp_ratio = float(self.param('tp_ratio', 2.0))

        close = df['close'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        vol = df['volume'].astype(float)

        # 2. 三档 EMA
        ema_f = close.ewm(span=ema_fast_p, adjust=False).mean()
        ema_m = close.ewm(span=ema_mid_p, adjust=False).mean()
        ema_s = close.ewm(span=ema_slow_p, adjust=False).mean()

        # 3. MACD
        macd_ind = ta.trend.MACD(close, window_slow=macd_slow,
                                 window_fast=macd_fast, window_sign=macd_sig)
        macd_line = macd_ind.macd()
        macd_signal = macd_ind.macd_signal()
        macd_hist = macd_ind.macd_diff()

        # 4. 量能均线 + ATR
        vol_ma = vol.rolling(vol_ma_len).mean()
        atr_series = self._calculate_atr(df, atr_len)

        # 5. 取最后两根做穿越检测
        cur_close = float(close.iloc[-1])
        cur_f, prev_f = float(ema_f.iloc[-1]), float(ema_f.iloc[-2])
        cur_m, prev_m = float(ema_m.iloc[-1]), float(ema_m.iloc[-2])
        cur_s, prev_s = float(ema_s.iloc[-1]), float(ema_s.iloc[-2])

        cur_vol = float(vol.iloc[-1])
        cur_vol_ma = float(vol_ma.iloc[-1]) if not pd.isna(vol_ma.iloc[-1]) else 0.0
        cur_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0

        cur_macd, prev_macd = float(macd_line.iloc[-1]), float(macd_line.iloc[-2])
        cur_sig, prev_sig = float(macd_signal.iloc[-1]), float(macd_signal.iloc[-2])
        cur_hist = float(macd_hist.iloc[-1]) if not pd.isna(macd_hist.iloc[-1]) else 0.0

        # 6. NaN 防御：慢线/MACD 需要足够数据才有效
        if any(pd.isna(x) for x in [cur_f, cur_m, cur_s, cur_macd, cur_sig,
                                     prev_macd, prev_sig]):
            return StrategySignal('hold', 0, '指标数据不足，跳过')

        # 7. 金叉/死叉检测（穿越 = 严格 prev<=curr 方向反转）
        bull_silver_cross = prev_f <= prev_m and cur_f > cur_m
        bull_golden_cross = prev_f <= prev_s and cur_f > cur_s
        bull_mid_cross = prev_m <= prev_s and cur_m > cur_s
        macd_bull_cross = prev_macd <= prev_sig and cur_macd > cur_sig

        bear_silver_cross = prev_f >= prev_m and cur_f < cur_m
        bear_golden_cross = prev_f >= prev_s and cur_f < cur_s
        bear_mid_cross = prev_m >= prev_s and cur_m < cur_s
        macd_bear_cross = prev_macd >= prev_sig and cur_macd < cur_sig

        # 8. 排列状态（非穿越但同向，给半分）
        bull_silver_align = cur_f > cur_m
        bull_golden_align = cur_f > cur_s
        bull_mid_align = cur_m > cur_s
        macd_bull_align = cur_macd > cur_sig or cur_hist > 0

        bear_silver_align = cur_f < cur_m
        bear_golden_align = cur_f < cur_s
        bear_mid_align = cur_m < cur_s
        macd_bear_align = cur_macd < cur_sig or cur_hist < 0

        # 9. 量能评分
        vol_ok_full = cur_vol_ma > 0 and cur_vol >= cur_vol_ma * vol_ratio
        vol_ok_half = cur_vol_ma > 0 and cur_vol >= cur_vol_ma * 1.0

        # 10. 价格相对慢线（趋势过滤）
        price_above_slow = cur_close > cur_s
        price_below_slow = cur_close < cur_s

        # 11. 多头共振评分
        bull_score = 0.0
        bull_score += self.W_SILVER * (1.0 if bull_silver_cross else 0.5 if bull_silver_align else 0.0)
        bull_score += self.W_GOLDEN * (1.0 if bull_golden_cross else 0.5 if bull_golden_align else 0.0)
        bull_score += self.W_MID * (1.0 if bull_mid_cross else 0.5 if bull_mid_align else 0.0)
        bull_score += self.W_MACD * (1.0 if macd_bull_cross else 0.5 if macd_bull_align else 0.0)
        bull_score += self.W_VOL * (1.0 if vol_ok_full else 0.5 if vol_ok_half else 0.0)
        bull_score += self.W_PRICE * (1.0 if price_above_slow else 0.0)

        # 12. 空头共振评分（镜像）
        bear_score = 0.0
        bear_score += self.W_SILVER * (1.0 if bear_silver_cross else 0.5 if bear_silver_align else 0.0)
        bear_score += self.W_GOLDEN * (1.0 if bear_golden_cross else 0.5 if bear_golden_align else 0.0)
        bear_score += self.W_MID * (1.0 if bear_mid_cross else 0.5 if bear_mid_align else 0.0)
        bear_score += self.W_MACD * (1.0 if macd_bear_cross else 0.5 if macd_bear_align else 0.0)
        bear_score += self.W_VOL * (1.0 if vol_ok_full else 0.5 if vol_ok_half else 0.0)
        bear_score += self.W_PRICE * (1.0 if price_below_slow else 0.0)

        # 13. detail 字段
        vol_ratio_actual = cur_vol / max(cur_vol_ma, 1e-9)
        detail = {
            'close': round(cur_close, 4),
            'ema_fast': round(cur_f, 4), 'ema_mid': round(cur_m, 4), 'ema_slow': round(cur_s, 4),
            'macd': round(cur_macd, 6), 'macd_signal': round(cur_sig, 6), 'macd_hist': round(cur_hist, 6),
            'vol': round(cur_vol, 2), 'vol_ma': round(cur_vol_ma, 2),
            'vol_ratio_actual': round(vol_ratio_actual, 3),
            'atr': round(cur_atr, 8),
            'bull_score': round(bull_score, 4), 'bear_score': round(bear_score, 4),
            'silver_cross_bull': bull_silver_cross, 'golden_cross_bull': bull_golden_cross,
            'silver_cross_bear': bear_silver_cross, 'golden_cross_bear': bear_golden_cross,
            'macd_bull_cross': macd_bull_cross, 'macd_bear_cross': macd_bear_cross,
            'price_above_slow': price_above_slow, 'price_below_slow': price_below_slow,
        }

        # 14. 持仓中的平仓判断（反向共振达 exit_score 即平，平仓不受冷却限制）
        cur_side = (position or {}).get('side') if position else None
        if cur_side == 'long' and bear_score >= exit_score:
            return StrategySignal('close_long', round(min(bear_score, 1.0), 4),
                                  f'空头共振达平仓阈值(bear={bear_score:.2f}>={exit_score})',
                                  detail, tp_mode=tp_mode)
        if cur_side == 'short' and bull_score >= exit_score:
            return StrategySignal('close_short', round(min(bull_score, 1.0), 4),
                                  f'多头共振达平仓阈值(bull={bull_score:.2f}>={exit_score})',
                                  detail, tp_mode=tp_mode)

        # 15. 冷却 + 日止损检查
        cooling_min = int(self.param('cooling_min', 5))
        cooling_long_ok = self._cooling_ok(symbol, 'buy', cooling_min, context)
        cooling_short_ok = self._cooling_ok(symbol, 'sell', cooling_min, context)
        daily_stop_ok = self._daily_stop_ok(symbol, context)

        # 16. 开仓：多头共振
        if bull_score >= min_score and price_above_slow and cooling_long_ok and daily_stop_ok:
            sl = cur_close - stop_loss_mul * cur_atr
            tp = (cur_close + tp_ratio * (cur_close - sl)) if tp_mode == 'fixed' else None
            reason = (f'多头共振 bull={bull_score:.2f}(>={min_score}) '
                      f'银叉={bull_silver_cross} 金叉={bull_golden_cross} '
                      f'MACD={macd_bull_cross} 放量={vol_ok_full}')
            return StrategySignal('buy', round(min(bull_score, 1.0), 4), reason, detail,
                                  round(sl, 8), round(tp, 8) if tp else None,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)

        # 17. 开仓：空头共振
        if bear_score >= min_score and price_below_slow and cooling_short_ok and daily_stop_ok:
            sl = cur_close + stop_loss_mul * cur_atr
            tp = (cur_close - tp_ratio * (sl - cur_close)) if tp_mode == 'fixed' else None
            reason = (f'空头共振 bear={bear_score:.2f}(>={min_score}) '
                      f'银叉={bear_silver_cross} 金叉={bear_golden_cross} '
                      f'MACD={macd_bear_cross} 放量={vol_ok_full}')
            return StrategySignal('sell', round(min(bear_score, 1.0), 4), reason, detail,
                                  round(sl, 8), round(tp, 8) if tp else None,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)

        # 18. 默认 hold
        bits = []
        if bull_score < min_score and bear_score < min_score:
            bits.append(f'共振不足(bull={bull_score:.2f},bear={bear_score:.2f}<{min_score})')
        if not daily_stop_ok:
            bits.append('当日止损达上限')
        if not cooling_long_ok and bull_score >= min_score:
            bits.append('多头冷却中')
        if not cooling_short_ok and bear_score >= min_score:
            bits.append('空头冷却中')
        return StrategySignal('hold', 0, ';'.join(bits) or '条件不满足', detail)

    # ---------- 工具方法 ----------
    @staticmethod
    def _calculate_atr(df, atr_len=14):
        """计算 ATR（真实波幅均值），返回与 df 等长的 Series"""
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        close = df['close'].astype(float)
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=atr_len, min_periods=atr_len).mean()

    def _cooling_ok(self, symbol, signal_type, cooling_min, context):
        """冷却检查：距上次同向开仓信号间隔 >= cooling_min 分钟"""
        if not context or not context.get('check_cooling'):
            return True
        from apps.strategy.models import SignalRecord
        from django.utils import timezone
        last_sig = SignalRecord.objects.filter(
            strategy=self.config, inst_id=symbol, signal=signal_type
        ).order_by('-created_at').first()
        if last_sig is None:
            return True
        return (timezone.now() - last_sig.created_at) >= timedelta(minutes=cooling_min)

    def _daily_stop_ok(self, symbol, context):
        """当日止损次数检查：达上限则禁止开仓（回测跳过；0=不限制；跨日重置）"""
        if not context or not context.get('check_cooling'):
            return True
        daily_max = int(self.param('daily_max_stop', 3))
        if daily_max <= 0:
            return True
        from apps.strategy.models import TrackedPosition
        from django.utils import timezone
        today = timezone.now().date()
        tp = TrackedPosition.objects.filter(
            strategy=self.config, inst_id=symbol
        ).first()
        if tp is None:
            return True
        if tp.daily_stop_date != today:
            return True
        return tp.daily_stop_count < daily_max
