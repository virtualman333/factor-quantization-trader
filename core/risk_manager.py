"""
风控管理器
提供仓位控制、亏损限制、下单频率控制等风险管理功能
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from core.exceptions import (
    DailyLossLimitExceeded, InsufficientBalance,
    OrderRejectedError, PositionLimitExceeded,
)

logger = logging.getLogger(__name__)


@dataclass
class RiskLimits:
    """风控参数"""
    max_position_pct: float = 0.2       # 单币种最大仓位占比
    max_order_value: float = 10000      # 单笔订单最大金额 (USDT)
    max_daily_loss: float = 500         # 每日最大亏损 (USDT)
    stop_loss_pct: float = 0.05         # 止损比例
    default_leverage: int = 3           # 默认杠杆
    min_order_interval: float = 1.0     # 最小下单间隔 (秒)
    max_positions: int = 5              # 最大同时持仓数
    max_daily_trades: int = 50          # 每日最大交易次数
    slippage_tolerance: float = 0.002   # 滑点容忍度


@dataclass
class PositionInfo:
    """持仓信息"""
    inst_id: str
    pos: float = 0.0         # 持仓数量
    avg_px: float = 0.0      # 开仓均价
    mark_px: float = 0.0     # 标记价格
    upl: float = 0.0         # 未实现盈亏
    margin: float = 0.0      # 保证金
    leverage: float = 1.0    # 杠杆


class RiskManager:
    """统一风控管理器"""

    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or self._load_limits()
        self._last_order_time: Dict[str, float] = {}
        self._daily_trades: int = 0
        self._daily_pnl: float = 0.0
        self._daily_reset_date: date = timezone.now().date()

        # 从缓存恢复今日交易统计
        self._load_daily_stats()

    @staticmethod
    def _load_limits() -> RiskLimits:
        """从配置加载风控参数"""
        cfg = settings.RISK_CONFIG
        return RiskLimits(
            max_position_pct=cfg.get('MAX_POSITION_PCT', 0.2),
            max_order_value=cfg.get('MAX_ORDER_VALUE', 10000),
            max_daily_loss=cfg.get('MAX_DAILY_LOSS', 500),
            stop_loss_pct=cfg.get('STOP_LOSS_PCT', 0.05),
            default_leverage=cfg.get('DEFAULT_LEVERAGE', 3),
            min_order_interval=cfg.get('MIN_ORDER_INTERVAL', 1.0),
        )

    def _check_daily_reset(self):
        """检查是否需要重置每日统计"""
        today = timezone.now().date()
        if today != self._daily_reset_date:
            self._daily_trades = 0
            self._daily_pnl = 0.0
            self._daily_reset_date = today
            self._save_daily_stats()

    def _load_daily_stats(self):
        """从缓存加载每日统计"""
        stats = cache.get('risk:daily_stats')
        if stats and stats.get('date') == str(timezone.now().date()):
            self._daily_trades = stats.get('trades', 0)
            self._daily_pnl = stats.get('pnl', 0.0)
            self._daily_reset_date = timezone.now().date()

    def _save_daily_stats(self):
        """保存每日统计到缓存"""
        cache.set('risk:daily_stats', {
            'date': str(self._daily_reset_date),
            'trades': self._daily_trades,
            'pnl': self._daily_pnl,
        }, timeout=86400)

    def record_trade(self, pnl: float = 0.0):
        """记录一次交易"""
        self._check_daily_reset()
        self._daily_trades += 1
        self._daily_pnl += pnl
        self._save_daily_stats()

    # ============ 下单前检查 ============
    def pre_order_check(self, inst_id: str, side: str, sz: float,
                        px: float, account_balance: float,
                        current_positions: Dict[str, PositionInfo]) -> bool:
        """下单前综合风控检查，全部通过返回 True"""
        self._check_daily_reset()

        # 1. 每日交易次数限制
        if self._daily_trades >= self.limits.max_daily_trades:
            raise OrderRejectedError(
                f'超过每日最大交易次数: {self.limits.max_daily_trades}')

        # 2. 每日亏损限制
        if self._daily_pnl <= -self.limits.max_daily_loss:
            raise DailyLossLimitExceeded(
                f'超过每日最大亏损: {self.limits.max_daily_loss} USD')

        # 3. 下单频率限制
        now = time.time()
        last = self._last_order_time.get(inst_id, 0)
        if now - last < self.limits.min_order_interval:
            raise OrderRejectedError(
                f'下单太频繁，请间隔 {self.limits.min_order_interval}s')
        self._last_order_time[inst_id] = now

        # 4. 单笔订单金额限制
        order_value = sz * px
        if order_value > self.limits.max_order_value:
            raise OrderRejectedError(
                f'订单金额 {order_value:.2f} 超过限制 {self.limits.max_order_value}')

        # 5. 余额检查
        if side == 'buy' and order_value > account_balance:
            raise InsufficientBalance(
                f'余额不足: 需要 {order_value:.2f}, 可用 {account_balance:.2f}')

        # 6. 最大持仓数检查
        if side == 'buy' and len(current_positions) >= self.limits.max_positions:
            raise PositionLimitExceeded(
                f'超过最大持仓数: {self.limits.max_positions}')

        # 7. 单币种仓位比例检查
        if side == 'buy' and inst_id in current_positions:
            pos = current_positions[inst_id]
            pos_value = pos.pos * pos.mark_px + order_value
            if account_balance > 0 and pos_value / account_balance > self.limits.max_position_pct:
                raise PositionLimitExceeded(
                    f'{inst_id} 仓位比例 {pos_value/account_balance:.1%} 超过限制 '
                    f'{self.limits.max_position_pct:.0%}')

        return True

    def check_stop_loss(self, position: PositionInfo) -> bool:
        """检查是否触发止损"""
        if position.avg_px <= 0 or position.pos == 0:
            return False
        pnl_pct = position.upl / (position.avg_px * abs(position.pos))
        return pnl_pct <= -self.limits.stop_loss_pct

    def get_stop_loss_price(self, position: PositionInfo, is_long: bool = True) -> float:
        """计算止损价格"""
        if is_long:
            return position.avg_px * (1 - self.limits.stop_loss_pct)
        else:
            return position.avg_px * (1 + self.limits.stop_loss_pct)
