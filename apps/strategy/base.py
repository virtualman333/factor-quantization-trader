"""
策略统一规范基类

新增策略只需三步：
1. 在 apps/strategy/strategies/ 下新建一个文件
2. 继承 BaseStrategy，实现 code/name/description/PARAM_SCHEMA
3. 实现 generate_signal()（返回信号）和 backtest_adapt()（可选，回测前的准备）

注册：用 @registry.register 装饰器装饰类，或用 registry.auto_discover() 自动扫描。
"""

import logging
from typing import Dict, List, Optional, Tuple

from apps.strategy.models import StrategyConfig

logger = logging.getLogger(__name__)


class ParamSchema:
    """策略参数 schema：清晰描述每个参数的元信息，前端据此动态渲染表单。"""

    def __init__(self, key, label, param_type='number', default=None,
                 min_value=None, max_value=None, step=None,
                 options=None, help_text='', required=True):
        self.key = key
        self.label = label
        self.param_type = param_type  # number / int / bool / choice / str
        self.default = default
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.options = options or []  # choice 类型的 [{value, label}]
        self.help_text = help_text
        self.required = required

    def to_dict(self):
        return {
            'key': self.key,
            'label': self.label,
            'type': self.param_type,
            'default': self.default,
            'min': self.min_value,
            'max': self.max_value,
            'step': self.step,
            'options': self.options,
            'help': self.help_text,
            'required': self.required,
        }


class StrategySignal:
    """统一信号返回对象"""

    def __init__(self, signal: str, score: float = 0.0, reason: str = '',
                 detail: Optional[Dict] = None,
                 stop_loss_price=None, take_profit_price=None,
                 entry_atr=None, tp_mode: str = ''):
        self.signal = signal          # buy / sell / close_long / close_short / hold
        self.score = score            # 0~1
        self.reason = reason
        self.detail = detail or {}
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
        self.entry_atr = entry_atr
        self.tp_mode = tp_mode

    @property
    def is_hold(self) -> bool:
        return self.signal == 'hold'

    def to_dict(self) -> Dict:
        return {
            'signal': self.signal,
            'score': round(float(self.score), 4),
            'reason': self.reason,
            'detail': self.detail,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'entry_atr': self.entry_atr,
            'tp_mode': self.tp_mode,
        }


class BaseStrategy:
    """所有策略的基类（策略规范）。"""

    # 策略标识（对应 StrategyConfig.strategy_type）
    code: str = ''
    # 策略显示名
    name: str = ''
    # 策略描述
    description: str = ''
    # 参数 schema（前端据此动态渲染参数表单）
    PARAM_SCHEMA: List[ParamSchema] = []
    # 需要的最小 K 线数量（数据不足跳过）
    MIN_BARS: int = 60

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.params = self._merge_params()

    # ---------- 参数 ----------
    @classmethod
    def default_params(cls) -> Dict:
        return {s.key: s.default for s in cls.PARAM_SCHEMA if s.default is not None}

    def _merge_params(self) -> Dict:
        """合并默认参数与用户配置（策略 params 字段优先）"""
        merged = self.default_params()
        user_params = (self.config.params or {})
        merged.update({k: v for k, v in user_params.items() if v is not None})
        return merged

    def param(self, key: str, default=None):
        """读取单个参数（含类型转换）"""
        val = self.params.get(key, default)
        schema = self._schema_map().get(key)
        if schema and val is not None:
            if schema.param_type == 'int':
                try:
                    return int(val)
                except (TypeError, ValueError):
                    return schema.default
            if schema.param_type == 'number':
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return schema.default
            if schema.param_type == 'bool':
                return bool(val)
        return val

    @classmethod
    def _schema_map(cls) -> Dict:
        return {s.key: s for s in cls.PARAM_SCHEMA}

    @classmethod
    def get_param_schema(cls) -> List[Dict]:
        """导出参数 schema 列表（前端渲染用）"""
        return [s.to_dict() for s in cls.PARAM_SCHEMA]

    # ---------- 信号生成 ----------
    def generate_signal(self, df, symbol: str, position: Optional[Dict] = None,
                        context: Optional[Dict] = None) -> StrategySignal:
        """核心接口：根据 K 线数据生成交易信号。

        Args:
            df: OHLCV DataFrame，index=timestamp，含 open/high/low/close/volume
            symbol: 交易标的
            position: 当前持仓信息 {'side': 'long'|'short', ...}，实盘来自 OKX，回测来自引擎
            context: 附加上下文（如实盘的用户、可用余额等）

        Returns:
            StrategySignal，signal ∈ buy/sell/close_long/close_short/hold
        """
        raise NotImplementedError('子类必须实现 generate_signal()')

    # ---------- 信号方向过滤 ----------
    def filter_by_direction(self, signal: str) -> str:
        """按策略方向过滤信号：方向只约束开仓，平仓不受限制"""
        direction = self.config.direction
        if signal in ('close_long', 'close_short', 'hold'):
            return signal
        if direction == 'long':
            return signal if signal in ('buy',) else 'hold'
        if direction == 'short':
            return signal if signal in ('sell',) else 'hold'
        return signal  # both

    @staticmethod
    def infer_pos_side(signal: str) -> str:
        """根据信号推断持仓方向"""
        if signal in ('buy', 'close_short'):
            return 'long'
        if signal in ('sell', 'close_long'):
            return 'short'
        return 'net'

    # ---------- 元信息 ----------
    @classmethod
    def meta(cls) -> Dict:
        return {
            'code': cls.code,
            'name': cls.name,
            'description': cls.description,
            'params': cls.get_param_schema(),
            'min_bars': cls.MIN_BARS,
        }
