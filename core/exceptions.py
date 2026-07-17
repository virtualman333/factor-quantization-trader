"""自定义异常"""


class QuantTradingError(Exception):
    """量化交易基础异常"""
    pass


class OKXClientError(QuantTradingError):
    """OKX 客户端异常"""
    pass


class OKXAuthError(OKXClientError):
    """OKX 认证异常"""
    pass


class RiskLimitExceeded(QuantTradingError):
    """超出风控限制"""
    pass


class InsufficientBalance(RiskLimitExceeded):
    """余额不足"""
    pass


class DailyLossLimitExceeded(RiskLimitExceeded):
    """超过每日亏损限制"""
    pass


class PositionLimitExceeded(RiskLimitExceeded):
    """超过持仓限制"""
    pass


class OrderRejectedError(QuantTradingError):
    """订单被拒绝"""
    pass


class MarketDataUnavailable(QuantTradingError):
    """行情数据不可用"""
    pass


class StrategyError(QuantTradingError):
    """策略执行错误"""
    pass
