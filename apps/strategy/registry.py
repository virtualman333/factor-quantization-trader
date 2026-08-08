"""
策略注册表：集中管理所有策略实现，支持运行时动态增减。

新增策略流程：
1. 在 apps/strategy/strategies/ 下新建 xxx.py
2. 继承 BaseStrategy，实现 code/name/generate_signal
3. 用 @registry.register 装饰器注册
注册后即可在 StrategyConfig.strategy_type 中选择，统一支持回测。
"""

import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Type

from apps.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """策略注册表（单例）"""

    def __init__(self):
        self._strategies: Dict[str, Type[BaseStrategy]] = {}
        self._discovered = False

    # ---------- 注册 ----------
    def register(self, cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
        """装饰器：注册策略类"""
        if not issubclass(cls, BaseStrategy):
            raise TypeError(f'{cls} 必须继承 BaseStrategy')
        if not cls.code:
            raise ValueError(f'{cls.__name__} 缺少 code 属性')
        self._strategies[cls.code] = cls
        logger.info(f'策略注册: {cls.code} -> {cls.name}')
        return cls

    def unregister(self, code: str):
        """移除策略（运行时动态增减）"""
        self._strategies.pop(code, None)
        logger.info(f'策略注销: {code}')

    # ---------- 自动发现 ----------
    def auto_discover(self, package: str = 'apps.strategy.strategies'):
        """自动扫描 strategies 包下的所有模块并导入（触发注册）"""
        if self._discovered:
            return
        try:
            pkg = importlib.import_module(package)
            for mod in pkgutil.iter_modules(pkg.__path__):
                if mod.name.startswith('_'):
                    continue
                try:
                    importlib.import_module(f'{package}.{mod.name}')
                except Exception as e:
                    logger.warning(f'加载策略模块 {mod.name} 失败: {e}')
            self._discovered = True
        except Exception as e:
            logger.warning(f'策略自动发现失败: {e}')

    # ---------- 查询 ----------
    def get(self, code: str) -> Optional[Type[BaseStrategy]]:
        self.auto_discover()
        return self._strategies.get(code)

    def get_or_error(self, code: str) -> Type[BaseStrategy]:
        cls = self.get(code)
        if cls is None:
            from core.exceptions import StrategyError
            raise StrategyError(f'未注册的策略类型: {code}')
        return cls

    def all(self) -> List[Type[BaseStrategy]]:
        self.auto_discover()
        return list(self._strategies.values())

    def codes(self) -> List[str]:
        return list(self._strategies.keys())

    def meta_list(self) -> List[Dict]:
        """所有策略的元信息列表（供前端策略类型下拉和动态参数表单）"""
        return [cls.meta() for cls in self.all()]


# 全局单例
registry = StrategyRegistry()
register = registry.register
