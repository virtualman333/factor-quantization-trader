"""
趋势跟踪策略
基于 EMA 金叉/死叉 + ADX 趋势强度生成信号。
"""

import logging

import pandas as pd
import ta

from apps.strategy.base import BaseStrategy, ParamSchema, StrategySignal
from apps.strategy.registry import register

logger = logging.getLogger(__name__)


@register
class TrendFollowStrategy(BaseStrategy):
    code = 'trend_follow'
    name = '趋势跟踪'
    description = 'EMA12/26 金叉死叉 + ADX 趋势强度过滤'
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
    ]

    def generate_signal(self, df, symbol, position=None, context=None):
        ema_fast = int(self.param('ema_fast', 12))
        ema_slow = int(self.param('ema_slow', 26))
        adx_period = int(self.param('adx_period', 14))
        adx_threshold = float(self.param('adx_threshold', 25))

        close = df['close']
        fast_ma = close.ewm(span=ema_fast, adjust=False).mean()
        slow_ma = close.ewm(span=ema_slow, adjust=False).mean()
        adx = ta.trend.ADXIndicator(
            df['high'], df['low'], df['close'], window=adx_period
        ).adx()

        last_close = float(close.iloc[-1])
        prev_fast = float(fast_ma.iloc[-2])
        prev_slow = float(slow_ma.iloc[-2])
        curr_fast = float(fast_ma.iloc[-1])
        curr_slow = float(slow_ma.iloc[-1])
        adx_value = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0

        score = min(adx_value / 50, 1.0) if adx_value > 20 else 0.3
        trend_strong = adx_value >= adx_threshold

        golden_cross = prev_fast <= prev_slow and curr_fast > curr_slow
        death_cross = prev_fast >= prev_slow and curr_fast < curr_slow
        above_ma = curr_fast > curr_slow and last_close > curr_fast
        below_ma = curr_fast < curr_slow and last_close < curr_fast

        cur_side = (position or {}).get('side') if position else None

        # 平仓：死叉/跌破慢线平多；金叉/突破慢线平空
        if cur_side == 'long' and (death_cross or (last_close < curr_slow)):
            return StrategySignal('close_long', 0.7,
                                  f'趋势反转/跌破均线，ADX={adx_value:.1f}')
        if cur_side == 'short' and (golden_cross or (last_close > curr_slow)):
            return StrategySignal('close_short', 0.7,
                                  f'趋势反转/突破均线，ADX={adx_value:.1f}')

        # 开仓
        if golden_cross or (above_ma and trend_strong):
            reason = f'EMA金叉且趋势强劲，ADX={adx_value:.1f}' if golden_cross \
                else f'均线多头排列，ADX={adx_value:.1f}'
            return StrategySignal('buy', score, reason)
        if death_cross or (below_ma and trend_strong):
            reason = f'EMA死叉且趋势强劲，ADX={adx_value:.1f}' if death_cross \
                else f'均线空头排列，ADX={adx_value:.1f}'
            return StrategySignal('sell', score, reason)

        return StrategySignal('hold', 0, f'无明确趋势，ADX={adx_value:.1f}')
