"""
订单服务层
提供下单、撤单、状态同步等功能
"""

import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from core.okx_client import get_okx_client
from core.risk_manager import RiskManager
from core.exceptions import OrderRejectedError
from apps.orders.models import TradeOrder, OrderLog

logger = logging.getLogger(__name__)


class OrderService:
    """订单管理服务"""

    @staticmethod
    def create_order(inst_id: str, side: str, ord_type: str, sz: str,
                     px: str = '', td_mode: str = 'cash',
                     pos_side: str = '', source: str = 'manual',
                     strategy_id: int = None, signal_id: int = None) -> Dict:
        """创建并提交订单"""
        # 风控检查
        risk_mgr = RiskManager()
        order_value = float(sz) * (float(px) if px else 0)
        if ord_type == 'market' and not px:
            # 市价单需要先获取价格
            client = get_okx_client()
            ticker = client.get_ticker(inst_id)
            if ticker['code'] == '0' and ticker['data']:
                order_value = float(sz) * float(ticker['data'][0]['last'])

        if order_value > 0:
            risk_mgr.pre_order_check(
                inst_id=inst_id, side=side, sz=float(sz),
                px=float(px or 0), account_balance=float('inf'),
                current_positions={},
            )

        # 生成客户订单ID
        cl_ord_id = f'qt_{uuid.uuid4().hex[:12]}'

        # 创建本地订单记录
        trade_order = TradeOrder.objects.create(
            cl_ord_id=cl_ord_id,
            inst_id=inst_id,
            td_mode=td_mode,
            side=side,
            ord_type=ord_type,
            sz=Decimal(str(sz)),
            px=Decimal(str(px)) if px else None,
            state='live',
            source=source,
            strategy_id=strategy_id,
            signal_id=signal_id,
        )
        OrderLog.objects.create(order=trade_order, action='created',
                                 detail={'cl_ord_id': cl_ord_id})

        # 提交到 OKX
        client = get_okx_client()
        result = client.place_order(
            inst_id=inst_id, td_mode=td_mode, side=side,
            ord_type=ord_type, sz=sz, px=px,
            pos_side=pos_side, client_oid=cl_ord_id,
        )

        if result['code'] == '0':
            data = result.get('data', [{}])[0]
            trade_order.ord_id = data.get('ordId', '')
            trade_order.state = 'live'
            trade_order.save()
            OrderLog.objects.create(order=trade_order, action='submitted',
                                     detail={'ord_id': trade_order.ord_id, 'result': result})
            logger.info(f'订单提交成功: {trade_order.ord_id}')
        else:
            trade_order.state = 'failed'
            trade_order.save()
            OrderLog.objects.create(order=trade_order, action='failed',
                                     detail={'error': result.get('msg')})
            raise OrderRejectedError(f'Order rejected: {result.get("msg")}')

        return {
            'ord_id': trade_order.ord_id,
            'cl_ord_id': trade_order.cl_ord_id,
            'state': trade_order.state,
            'result': result,
        }

    @staticmethod
    def cancel_order(ord_id: str, inst_id: str = '') -> Dict:
        """撤销订单"""
        client = get_okx_client()

        # 查找本地订单
        trade_order = TradeOrder.objects.filter(
            ord_id=ord_id, state__in=['live', 'partially_filled']
        ).first()

        if not trade_order:
            raise OrderRejectedError(f'未找到活跃订单: {ord_id}')

        result = client.cancel_order(
            inst_id=inst_id or trade_order.inst_id, ord_id=ord_id
        )

        if result['code'] == '0':
            trade_order.state = 'canceled'
            trade_order.save()
            OrderLog.objects.create(
                order=trade_order, action='canceled',
                detail={'ord_id': ord_id, 'result': result}
            )
            logger.info(f'订单撤单成功: {ord_id}')

        return {'ord_id': ord_id, 'state': trade_order.state, 'result': result}

    @staticmethod
    def sync_order_status(ord_id: str) -> Optional[TradeOrder]:
        """同步单个订单状态"""
        trade_order = TradeOrder.objects.filter(ord_id=ord_id).first()
        if not trade_order:
            logger.warning(f'未找到本地订单: {ord_id}')
            return None

        client = get_okx_client()
        result = client.get_order(
            inst_id=trade_order.inst_id, ord_id=ord_id
        )

        if result['code'] != '0':
            logger.error(f'查询订单 {ord_id} 失败: {result.get("msg")}')
            return trade_order

        data = result.get('data', [])
        if not data:
            return trade_order

        item = data[0]
        new_state = item.get('state', trade_order.state)

        if new_state != trade_order.state:
            old_state = trade_order.state
            trade_order.state = new_state
            trade_order.fill_sz = Decimal(str(item.get('fillSz', 0)))
            trade_order.fill_px = Decimal(str(item.get('fillPx', 0))) if item.get('fillPx') else None
            trade_order.fee = Decimal(str(item.get('fee', 0)))
            trade_order.fee_ccy = item.get('feeCcy', '')

            if new_state == 'filled':
                trade_order.filled_at = timezone.now()

            trade_order.save()

            OrderLog.objects.create(
                order=trade_order,
                action='filled' if new_state == 'filled' else new_state,
                detail={
                    'old_state': old_state,
                    'new_state': new_state,
                    'fill_sz': str(trade_order.fill_sz),
                    'fill_px': str(trade_order.fill_px) if trade_order.fill_px else None,
                }
            )
            logger.info(f'订单 {ord_id} 状态变更: {old_state} -> {new_state}')

        return trade_order

    @staticmethod
    def sync_pending_orders() -> int:
        """同步所有待处理订单状态"""
        pending = TradeOrder.objects.filter(
            state__in=['live', 'partially_filled']
        )
        count = 0
        for order in pending:
            try:
                OrderService.sync_order_status(order.ord_id)
                count += 1
            except Exception as e:
                logger.error(f'同步订单 {order.ord_id} 失败: {e}')
        return count

    @staticmethod
    def place_market_close(inst_id: str, sz: str, side: str = '',
                           td_mode: str = 'cash', source: str = 'strategy') -> Dict:
        """市价平仓"""
        if not side:
            # 根据持仓方向决定
            from apps.account.services import AccountService
            positions = AccountService.get_positions_from_api()
            pos = positions.get(inst_id)
            if pos:
                side = 'sell' if pos.pos > 0 else 'buy'
            else:
                raise OrderRejectedError(f'无 {inst_id} 持仓')

        return OrderService.create_order(
            inst_id=inst_id,
            side=side,
            ord_type='market',
            sz=sz,
            td_mode=td_mode,
            source=source,
        )
