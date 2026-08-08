"""
放量跟随策略
放量上涨/下跌 + 趋势过滤 + ATR 过滤 + 冷却 生成信号，支持止损止盈参数。
"""

import logging
from datetime import timedelta

import pandas as pd

from apps.strategy.base import BaseStrategy, ParamSchema, StrategySignal
from apps.strategy.registry import register

logger = logging.getLogger(__name__)


@register
class VolumeBreakoutStrategy(BaseStrategy):
    code = 'volume_breakout'
    name = '放量跟随'
    description = '放量上涨做多/放量下跌做空，含趋势过滤、ATR过滤、冷却与止损止盈'
    MIN_BARS = 60

    PARAM_SCHEMA = [
        ParamSchema('vol_ma_len', '成交量均线周期', 'int', 20, 2, 200, 1,
                    help_text='成交量均线周期'),
        ParamSchema('vol_ratio', '放量倍数阈值', 'number', 1.8, 1.0, 10, 0.1,
                    help_text='当前量 >= 均量 × 该倍数 视为放量'),
        ParamSchema('trend_ma_len', '趋势均线周期', 'int', 60, 5, 500, 1,
                    help_text='大方向均线（震荡过滤）'),
        ParamSchema('atr_len', 'ATR周期', 'int', 14, 2, 100, 1,
                    help_text='ATR 计算周期'),
        ParamSchema('min_atr_factor', '最小波动阈值', 'number', 0.0015, 0, 0.02, 0.0001,
                    help_text='ATR/价格 低于该值则震荡屏蔽'),
        ParamSchema('cooling_min', '冷却时间(分钟)', 'int', 3, 1, 60, 1,
                    help_text='同方向信号最小间隔'),
        ParamSchema('stop_loss_mul', '止损倍数', 'number', 1.2, 0.1, 5, 0.1,
                    help_text='止损距离 = 倍数 × entry_atr'),
        ParamSchema('tp_mode', '止盈模式', 'choice', 'fixed',
                    options=[{'value': 'fixed', 'label': '固定盈亏比'},
                             {'value': 'trailing', 'label': '移动止盈'}],
                    help_text='固定盈亏比 或 移动止盈'),
        ParamSchema('tp_ratio', '固定止盈盈亏比', 'number', 1.5, 0.5, 10, 0.1,
                    help_text='固定止盈模式下：盈利 = 盈亏比 × 止损距离'),
        ParamSchema('trailing_trigger', '移动止盈触发倍数', 'number', 0.5, 0.1, 2, 0.1,
                    help_text='盈利达 该倍数×止损距离 启动移动止盈'),
        ParamSchema('trailing_factor', '移动追踪幅度', 'number', 0.8, 0.1, 3, 0.1,
                    help_text='追踪幅度 = 因子 × entry_atr'),
        ParamSchema('enhanced_no_single_pulse', '拒绝单根脉冲K', 'bool', False,
                    help_text='要求前一根成交量 >= 均量×1.2，过滤单根脉冲'),
        ParamSchema('risk_per_trade', '单笔风险比例', 'number', 0.01, 0.001, 0.05, 0.001,
                    help_text='仓位 = 资金×比例 ÷ 止损距离'),
        ParamSchema('daily_max_stop', '单日最大止损', 'int', 3, 0, 10, 1,
                    help_text='达上限当日停止开仓'),
    ]

    def generate_signal(self, df, symbol, position=None, context=None):
        """根据最新一根K线判断是否放量突破"""
        vol_ma_len = int(self.param('vol_ma_len', 20))
        vol_ratio = float(self.param('vol_ratio', 1.8))
        trend_ma_len = int(self.param('trend_ma_len', 60))
        atr_len = int(self.param('atr_len', 14))
        min_atr_factor = float(self.param('min_atr_factor', 0.0015))
        enhanced1 = bool(self.param('enhanced_no_single_pulse', False))
        stop_loss_mul = float(self.param('stop_loss_mul', 1.2))
        tp_mode = self.param('tp_mode', 'fixed')
        tp_ratio = float(self.param('tp_ratio', 1.5))

        close = df['close'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        vol = df['volume'].astype(float)
        op = df['open'].astype(float)

        vol_ma = vol.rolling(vol_ma_len).mean()
        ma_trend = close.rolling(trend_ma_len).mean()
        atr_series = self._calculate_atr(df, atr_len)

        cur_vol = float(vol.iloc[-1])
        cur_vol_ma = float(vol_ma.iloc[-1])
        prev_vol = float(vol.iloc[-2]) if len(vol) > 1 else 0
        cur_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0
        cur_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2]) if len(close) > 1 else cur_close
        cur_open = float(op.iloc[-1])
        cur_ma = float(ma_trend.iloc[-1])

        is_burst = cur_vol_ma > 0 and cur_vol > cur_vol_ma * vol_ratio
        prev_burst_ok = True
        if enhanced1:
            prev_burst_ok = prev_vol >= cur_vol_ma * 1.2

        is_bull_k = (cur_close > cur_open) and (cur_close > prev_close)
        is_bear_k = (cur_close < cur_open) and (cur_close < prev_close)
        bull_signal = is_burst and is_bull_k and prev_burst_ok
        bear_signal = is_burst and is_bear_k and prev_burst_ok

        atr_ok = cur_atr > 0 and cur_atr > min_atr_factor * cur_close
        above_ma = cur_close > cur_ma
        below_ma = cur_close < cur_ma

        # 冷却检查
        cooling_min = int(self.param('cooling_min', 3))
        cooling_long_ok = self._cooling_ok(symbol, 'buy', cooling_min, context)
        cooling_short_ok = self._cooling_ok(symbol, 'sell', cooling_min, context)

        # 止损/止盈价计算
        stop_loss_price = take_profit_price = None
        if bull_signal or bear_signal:
            if bull_signal:
                sl = cur_close - stop_loss_mul * cur_atr
                tp = (cur_close + tp_ratio * (cur_close - sl)) if tp_mode == 'fixed' else None
            else:
                sl = cur_close + stop_loss_mul * cur_atr
                tp = (cur_close - tp_ratio * (sl - cur_close)) if tp_mode == 'fixed' else None
            stop_loss_price = round(sl, 8)
            take_profit_price = round(tp, 8) if tp else None

        detail = {
            'vol': round(cur_vol, 2),
            'vol_ma': round(cur_vol_ma, 2),
            'close': round(cur_close, 4),
            'ma': round(cur_ma, 4),
            'atr': round(cur_atr, 8),
            'bull_signal': bull_signal,
            'bear_signal': bear_signal,
            'atr_ok': atr_ok,
            'above_ma': above_ma,
        }

        cur_side = (position or {}).get('side') if position else None

        if cur_side == 'long' and bear_signal:
            return StrategySignal('close_long', 0.8,
                                  '持有多仓 + 触发空头放量信号 -> 强制平多',
                                  detail, stop_loss_price, take_profit_price,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)
        if cur_side == 'short' and bull_signal:
            return StrategySignal('close_short', 0.8,
                                  '持有空仓 + 触发多头放量信号 -> 强制平空',
                                  detail, stop_loss_price, take_profit_price,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)

        # 无持仓时开仓
        if bull_signal and above_ma and atr_ok and cooling_long_ok:
            return StrategySignal('buy', 0.8,
                                  f'放量上涨+顺势(价>MA{trend_ma_len})+ATR过滤',
                                  detail, stop_loss_price, take_profit_price,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)
        if bear_signal and below_ma and atr_ok and cooling_short_ok:
            return StrategySignal('sell', 0.8,
                                  f'放量下跌+顺势(价<MA{trend_ma_len})+ATR过滤',
                                  detail, stop_loss_price, take_profit_price,
                                  round(cur_atr, 8) if cur_atr else None, tp_mode)

        bits = []
        if not (bull_signal or bear_signal):
            bits.append('无放量同向K')
        if not atr_ok:
            bits.append('ATR过小/震荡屏蔽')
        if not (above_ma or below_ma):
            bits.append('价格缠绕MA')
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
