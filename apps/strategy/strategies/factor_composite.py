"""
因子综合评分策略
基于多个技术因子的加权综合评分生成信号（buy/sell/hold），含 ATR 止损止盈、平仓逻辑、冷却与日止损。
"""

import logging
from datetime import timedelta

import pandas as pd

from apps.strategy.base import BaseStrategy, ParamSchema, StrategySignal
from apps.strategy.factors import FactorEngine
from apps.strategy.registry import register

logger = logging.getLogger(__name__)


@register
class FactorCompositeStrategy(BaseStrategy):
    code = 'factor_composite'
    name = '因子综合评分'
    description = '多技术因子加权综合评分：得分>=0.65买入，<=0.35卖出，含ATR止损止盈'
    MIN_BARS = 60

    PARAM_SCHEMA = [
        ParamSchema('buy_threshold', '买入阈值', 'number', 0.65, 0.5, 0.9, 0.05,
                    help_text='综合评分 >= 该值 触发买入'),
        ParamSchema('sell_threshold', '卖出阈值', 'number', 0.35, 0.1, 0.5, 0.05,
                    help_text='综合评分 <= 该值 触发卖出'),
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
        # ---- 平仓阈值（新增） ----
        ParamSchema('exit_threshold', '平仓评分阈值', 'number', 0.45, 0.1, 0.6, 0.05,
                    help_text='持仓中反向评分穿越该值时平仓'),
        # ---- 风控：冷却与日止损（新增） ----
        ParamSchema('cooling_min', '冷却时间(分钟)', 'int', 5, 1, 120, 1,
                    help_text='同方向信号最小间隔'),
        ParamSchema('daily_max_stop', '单日最大止损', 'int', 3, 0, 10, 1,
                    help_text='该标的当日止损达上限后停止开仓（0=不限制）'),
    ]

    def generate_signal(self, df, symbol, position=None, context=None):
        engine = FactorEngine(df)
        factor_list = list(self.config.factors or [])
        # 注册用户自定义因子
        custom_factors = context.get('custom_factors', []) if context else []
        for cf in custom_factors:
            engine.set_custom_formula(cf['name'], cf['formula'])
            factor_list.append(cf['name'])

        engine.calculate_all(factor_list)
        weights = self.config.factor_weights or None
        composite_score, composite_signal = engine.get_composite_score(weights=weights)

        buy_th = float(self.param('buy_threshold', 0.65))
        sell_th = float(self.param('sell_threshold', 0.35))
        exit_th = float(self.param('exit_threshold', 0.45))
        atr_len = int(self.param('atr_len', 14))
        stop_loss_mul = float(self.param('stop_loss_mul', 1.5))
        tp_mode = self.param('tp_mode', 'fixed')
        tp_ratio = float(self.param('tp_ratio', 2.0))
        cooling_min = int(self.param('cooling_min', 5))

        # ATR 计算（止损止盈用）
        atr_series = self._calculate_atr(df, atr_len)
        cur_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0
        cur_close = float(df['close'].iloc[-1])

        details = {
            name: {'value': r.value, 'score': round(r.score, 4), 'signal': r.signal}
            for name, r in engine._results.items()
        }
        details['composite_score'] = round(float(composite_score), 4)
        details['atr'] = round(cur_atr, 8)

        # 持仓中的平仓判断（平仓不受冷却限制）
        cur_side = (position or {}).get('side') if position else None
        if cur_side == 'long' and composite_score <= exit_th:
            return StrategySignal(
                'close_long', round(min(1 - composite_score, 1.0), 4),
                f'综合评分回落至平仓区({composite_score:.2f}<={exit_th})',
                details, tp_mode=tp_mode,
            )
        if cur_side == 'short' and composite_score >= (1 - exit_th):
            return StrategySignal(
                'close_short', round(min(composite_score, 1.0), 4),
                f'综合评分回升至平仓区({composite_score:.2f}>={1 - exit_th:.2f})',
                details, tp_mode=tp_mode,
            )

        # 开仓信号方向
        if composite_score >= buy_th:
            signal = 'buy'
        elif composite_score <= sell_th:
            signal = 'sell'
        else:
            signal = 'hold'

        # 冷却 + 日止损检查（仅开仓时检查）
        if signal in ('buy', 'sell'):
            cooling_ok = self._cooling_ok(symbol, signal, cooling_min, context)
            daily_stop_ok = self._daily_stop_ok(symbol, context)
            details['cooling_ok'] = cooling_ok
            details['daily_stop_ok'] = daily_stop_ok
            if not cooling_ok or not daily_stop_ok:
                bits = []
                if not cooling_ok:
                    bits.append(f'{signal}冷却中')
                if not daily_stop_ok:
                    bits.append('当日止损达上限')
                return StrategySignal('hold', 0,
                                      f'评分={composite_score:.2f} 但 {";".join(bits)}',
                                      details)
            # 止损止盈价计算
            sl = tp = None
            if signal == 'buy':
                sl = cur_close - stop_loss_mul * cur_atr
                tp = (cur_close + tp_ratio * (cur_close - sl)) if tp_mode == 'fixed' else None
            else:
                sl = cur_close + stop_loss_mul * cur_atr
                tp = (cur_close - tp_ratio * (sl - cur_close)) if tp_mode == 'fixed' else None
            return StrategySignal(
                signal=signal,
                score=float(composite_score),
                reason=f'综合评分: {composite_score:.2f}, 成分: {composite_signal}',
                detail=details,
                stop_loss_price=round(sl, 8) if sl is not None else None,
                take_profit_price=round(tp, 8) if tp is not None else None,
                entry_atr=round(cur_atr, 8) if cur_atr else None,
                tp_mode=tp_mode,
            )

        return StrategySignal(
            signal='hold',
            score=float(composite_score),
            reason=f'综合评分: {composite_score:.2f} 处于中性区({sell_th}~{buy_th})',
            detail=details,
        )

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
