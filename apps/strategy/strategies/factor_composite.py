"""
因子综合评分策略
基于多个技术因子的加权综合评分生成信号（buy/sell/hold）。
"""

import logging

from apps.strategy.base import BaseStrategy, ParamSchema, StrategySignal
from apps.strategy.factors import FactorEngine
from apps.strategy.registry import register

logger = logging.getLogger(__name__)


@register
class FactorCompositeStrategy(BaseStrategy):
    code = 'factor_composite'
    name = '因子综合评分'
    description = '多技术因子加权综合评分：得分>=0.65买入，<=0.35卖出'
    MIN_BARS = 60

    PARAM_SCHEMA = [
        ParamSchema('buy_threshold', '买入阈值', 'number', 0.65, 0.5, 0.9, 0.05,
                    help_text='综合评分 >= 该值 触发买入'),
        ParamSchema('sell_threshold', '卖出阈值', 'number', 0.35, 0.1, 0.5, 0.05,
                    help_text='综合评分 <= 该值 触发卖出'),
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

        if composite_score >= buy_th:
            signal = 'buy'
        elif composite_score <= sell_th:
            signal = 'sell'
        else:
            signal = 'hold'

        details = {
            name: {'value': r.value, 'score': round(r.score, 4), 'signal': r.signal}
            for name, r in engine._results.items()
        }
        return StrategySignal(
            signal=signal,
            score=float(composite_score),
            reason=f'综合评分: {composite_score:.2f}, 成分: {composite_signal}',
            detail=details,
        )
