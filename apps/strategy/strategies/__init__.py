"""
策略实现包：所有策略模块放入本目录并注册到注册表。
"""

from apps.strategy.registry import registry
import apps.strategy.strategies.factor_composite   # noqa: F401
import apps.strategy.strategies.golden_cross        # noqa: F401
import apps.strategy.strategies.trend_follow        # noqa: F401
import apps.strategy.strategies.volume_breakout     # noqa: F401

# 自动发现未来新增的策略模块
registry.auto_discover()
