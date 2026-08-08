"""
趋势跟踪策略
基于 EMA 金叉/死叉 + ADX 趋势强度生成信号，含 ATR 止损止盈、量能确认、冷却与日止损。
"""

import logging
from datetime import timedelta

import pandas as pd
import ta

from apps.strategy.base import BaseStrategy, ParamSchema, StrategySignal
from apps.strategy.registry import register

logger = logging.getLogger(__name__)


@register
class TrendFollowStrategy(BaseStrategy):
    code = 'trend_follow'
    name = '趋势跟踪'
    description = 'EMA 金叉死叉 + ADX 趋势强度过滤 + ATR 止损止盈'
    MIN_BARS = 60

    PARAM_SCHEMA = [
        ParamSchema('ema_fast', '快线周期', 'int', 12, 3, 50, 1,
                    help_text='快速 EMA 周期'),
        ParamSchema('ema_slow', '慢线周期', 'int', 26, 10, 200, 1,
                    help_text='慢速 EMA 周期'),
        ParamSchema('adx_period', 'ADX周期', 'int', 14, 5, 60, 1,
                    help_text='ADX 趋势强度计算周期'),
        ParamSchema('adx_threshold', 'ADX趋势阈值', 'number', 25, 10, 50, 1,
                    help_text='ADX >= 该值认为趋势强劲，可开仓'),
        # ---- ATR 止损止盈（新增） ----
        ParamSchema('atr_len', 'ATR周期', 'int', 14, 2, 100, 1,
                    help_text='ATR 计算周期（止损止盈用）'),
        ParamSchema('stop_loss_mul', '止损倍数', 'number', 1.5, 0.1, 5.0, 0.1,
                    help_text='止损距离 = 倍数 × entry_atr'),
        ParamSchema('tp_mode', '止盈模式', 'choice', 'fixed',
                    options=[{'value': 'fixed', 'label': '固定盈亏比'},
                             {'value': 'trailing', 'label': '移动止盈'}],
                    help_text='固定盈亏比 或 移动止盈'),
        ParamSchema('tp_ratio', '固定止盈盈亏比', 'number', 2.0, 0.5, 10.0, 0.1,
                    help_text='固定止盈模式下：盈利 = 盈亏比 × 止损距离'),
        # ---- 量能确认（新增，可选开关） ----
        ParamSchema('vol_confirm', '量能确认开关', 'bool', False,
                    help_text='开启后要求当前量 >= 量均线×1.2 才开仓'),
        ParamSchema('vol_ma_len', '量能均线周期', 'int', 20, 5, 100, 1,
                    help_text='成交量均线周期（vol_confirm 开启时生效）'),
        # ---- 风控：冷却与日止损（新增） ----
        ParamSchema('cooling_min', '冷却时间(分钟)', 'int', 5, 1, 120, 1,
                    help_text='同方向信号最小间隔'),
        ParamSchema('daily_max_stop', '单日最大止损', 'int', 3, 0, 10, 1,
                    help_text='该标的当日止损达上限后停止开仓（0=不限制）'),
    ]

    def generate_signal(self, df, symbol, position=None, context=None):
        ema_fast = int(self.param('ema_fast', 12))
        ema_slow = int(self.param('ema_slow', 26))
        adx_period = int(self.param('adx_period', 14))
        adx_threshold = float(self.param('adx_threshold', 25))
        atr_len = int(self.param('atr_len', 14))
        stop_loss_mul = float(self.param('stop_loss_mul', 1.5))
        tp_mode = self.param('tp_mode', 'fixed')
        tp_ratio = float(self.param('tp_ratio', 2.0))
        vol_confirm = bool(self.param('vol_confirm', False))
        cooling_min = int(self.param('cooling_min', 5))

        close = df['close'].astype(float)
        fast_ma = close.ewm(span=ema_fast, adjust=False).mean()
        slow_ma = close.ewm(span=ema_slow, adjust=False).mean()
        adx = ta.trend.ADXIndicator(
            df['high'], df['low'], df['close'], window=adx_period
        ).adx()
        atr_series = self._calculate_atr(df, atr_len)

        last_close = float(close.iloc[-1])
        prev_fast = float(fast_ma.iloc[-2])
        prev_slow = float(slow_ma.iloc[-2])
        curr_fast = float(fast_ma.iloc[-1])
        curr_slow = float(slow_ma.iloc[-1])
        adx_value = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0
        cur_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0

        # score 精细化：ADX 强度 60% + 穿越/排列 40%
        adx_denom = max(50 - adx_threshold, 1e-9)
        adx_score = min(max((adx_value - adx_threshold) / adx_denom, 0), 1.0)

        trend_strong = adx_value >= adx_threshold

        golden_cross = prev_fast <= prev_slow and curr_fast > curr_slow
        death_cross = prev_fast >= prev_slow and curr_fast < curr_slow
        above_ma = curr_fast > curr_slow and last_close > curr_fast
        below_ma = curr_fast < curr_slow and last_close < curr_fast

        # 量能确认（可选开关，默认关闭保持向后兼容）
        vol_ok = True
        cur_vol = cur_vol_ma = 0.0
        if vol_confirm:
            vol_ma_len = int(self.param('vol_ma_len', 20))
            vol_ma = df['volume'].astype(float).rolling(vol_ma_len).mean()
            cur_vol = float(df['volume'].iloc[-1])
            cur_vol_ma = float(vol_ma.iloc[-1]) if not pd.isna(vol_ma.iloc[-1]) else 0.0
            vol_ok = cur_vol_ma > 0 and cur_vol >= cur_vol_ma * 1.2

        # 冷却 + 日止损检查
        cooling_long_ok = self._cooling_ok(symbol, 'buy', cooling_min, context)
        cooling_short_ok = self._cooling_ok(symbol, 'sell', cooling_min, context)
        daily_stop_ok = self._daily_stop_ok(symbol, context)

        detail = {
            'close': round(last_close, 4),
            'ema_fast': round(curr_fast, 4),
            'ema_slow': round(curr_slow, 4),
            'adx': round(adx_value, 2),
            'atr': round(cur_atr, 8),
            'golden_cross': golden_cross,
            'death_cross': death_cross,
            'trend_strong': trend_strong,
            'vol_ok': vol_ok,
            'cooling_long_ok': cooling_long_ok,
            'cooling_short_ok': cooling_short_ok,
            'daily_stop_ok': daily_stop_ok,
        }

        cur_side = (position or {}).get('side') if position else None

        # 平仓：死叉/跌破慢线平多；金叉/突破慢线平空（平仓不受冷却限制）
        if cur_side == 'long' and (death_cross or (last_close < curr_slow)):
            return StrategySignal('close_long', 0.7,
                                  f'趋势反转/跌破均线，ADX={adx_value:.1f}',
                                  detail, tp_mode=tp_mode)
        if cur_side == 'short' and (golden_cross or (last_close > curr_slow)):
            return StrategySignal('close_short', 0.7,
                                  f'趋势反转/突破均线，ADX={adx_value:.1f}',
                                  detail, tp_mode=tp_mode)

        # score 计算（穿越满分，排列半分）
        cross_bonus = 1.0 if (golden_cross or death_cross) else 0.5
        score = round(min(max(0.6 * adx_score + 0.4 * cross_bonus, 0.0), 1.0), 4)

        # 开仓：多头
        if (golden_cross or (above_ma and trend_strong)) and vol_ok \
                and cooling_long_ok and daily_stop_ok:
            sl = last_close - stop_loss_mul * cur_atr
            tp = (last_close + tp_ratio * (last_close - sl)) if tp_mode == 'fixed' else None
            reason = f'EMA金叉且趋势强劲，ADX={adx_value:.1f}' if golden_cross \
                else f'均线多头排列，ADX={adx_value:.1f}'
            return StrategySignal('buy', score, reason, detail,
                                  round(sl, 8), round(tp, 8) if tp else None,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)
        # 开仓：空头
        if (death_cross or (below_ma and trend_strong)) and vol_ok \
                and cooling_short_ok and daily_stop_ok:
            sl = last_close + stop_loss_mul * cur_atr
            tp = (last_close - tp_ratio * (sl - last_close)) if tp_mode == 'fixed' else None
            reason = f'EMA死叉且趋势强劲，ADX={adx_value:.1f}' if death_cross \
                else f'均线空头排列，ADX={adx_value:.1f}'
            return StrategySignal('sell', score, reason, detail,
                                  round(sl, 8), round(tp, 8) if tp else None,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)

        bits = [f'无明确趋势，ADX={adx_value:.1f}']
        if not vol_ok:
            bits.append('量能不足')
        if not daily_stop_ok:
            bits.append('当日止损达上限')
        if not cooling_long_ok and (golden_cross or above_ma):
            bits.append('多头冷却中')
        if not cooling_short_ok and (death_cross or below_ma):
            bits.append('空头冷却中')
        return StrategySignal('hold', 0, ';'.join(bits), detail)

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
