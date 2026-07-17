"""
账户服务层
提供余额查询、持仓查询、净值记录等功能
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.utils import timezone

from core.okx_client import get_okx_client
from core.risk_manager import PositionInfo
from apps.account.models import BalanceSnapshot, PositionSnapshot, NetValueHistory

logger = logging.getLogger(__name__)


class AccountService:
    """账户管理服务"""

    @staticmethod
    def get_balance_from_api() -> Dict:
        """从 OKX 获取实时余额"""
        client = get_okx_client()
        result = client.get_account_balance()
        if result['code'] != '0':
            raise Exception(f'获取余额失败: {result.get("msg")}')

        total_eq_usd = Decimal('0')
        details = []
        for item in result.get('data', [])[0].get('details', []):
            eq = Decimal(str(item.get('cashBal', item.get('eq', '0'))))
            avail = Decimal(str(item.get('availBal', item.get('availEq', '0'))))
            frozen = Decimal(str(item.get('frozenBal', '0')))
            usd_val = Decimal(str(item.get('usdPnl', item.get('usdEq', '0'))))
            details.append({
                'ccy': item['ccy'],
                'total_eq': eq,
                'avail_eq': avail,
                'frozen_bal': frozen,
                'usd_value': usd_val,
            })
            total_eq_usd += usd_val

        return {
            'total_eq_usd': total_eq_usd,
            'details': details,
            'snapshot_time': timezone.now(),
        }

    @staticmethod
    def get_positions_from_api(inst_type: str = '') -> Dict:
        """从 OKX 获取实时持仓"""
        client = get_okx_client()
        result = client.get_positions(inst_type=inst_type)
        if result['code'] != '0':
            raise Exception(f'获取持仓失败: {result.get("msg")}')

        positions = {}
        for item in result.get('data', []):
            # 过滤零持仓
            pos_qty = float(item.get('pos', 0))
            if pos_qty == 0:
                continue

            inst_id = item['instId']
            positions[inst_id] = PositionInfo(
                inst_id=inst_id,
                pos=pos_qty,
                avg_px=float(item.get('avgPx', 0)),
                mark_px=float(item.get('markPx', 0)),
                upl=float(item.get('upl', 0)),
                margin=float(item.get('margin', 0)),
                leverage=float(item.get('lever', 1)),
            )
        return positions

    @staticmethod
    def snapshot_balance() -> List[BalanceSnapshot]:
        """保存余额快照"""
        balance = AccountService.get_balance_from_api()
        snapshots = []
        for detail in balance['details']:
            snap = BalanceSnapshot.objects.create(
                ccy=detail['ccy'],
                total_eq=detail['total_eq'],
                avail_eq=detail['avail_eq'],
                frozen_bal=detail['frozen_bal'],
                usd_value=detail['usd_value'],
                snapshot_time=timezone.now(),
            )
            snapshots.append(snap)
        logger.info(f'余额快照保存完成，共 {len(snapshots)} 币种，总权益 ${balance["total_eq_usd"]}')
        return snapshots

    @staticmethod
    def snapshot_positions(inst_type: str = '') -> List[PositionSnapshot]:
        """保存持仓快照"""
        positions = AccountService.get_positions_from_api(inst_type)
        snapshots = []
        for pos in positions.values():
            snap = PositionSnapshot.objects.create(
                inst_id=pos.inst_id,
                inst_type=inst_type or 'SWAP',
                pos_side='long' if pos.pos > 0 else 'short',
                pos=Decimal(str(abs(pos.pos))),
                avg_px=Decimal(str(pos.avg_px)),
                mark_px=Decimal(str(pos.mark_px)),
                upl=Decimal(str(pos.upl)),
                margin=Decimal(str(pos.margin)),
                leverage=Decimal(str(pos.leverage)),
            )
            snapshots.append(snap)
        logger.info(f'持仓快照保存完成，共 {len(snapshots)} 个持仓')
        return snapshots

    @staticmethod
    def record_net_value() -> NetValueHistory:
        """记录净值"""
        balance = AccountService.get_balance_from_api()
        total_eq_usd = balance['total_eq_usd']

        last_record = NetValueHistory.objects.order_by('-record_time').first()
        daily_pnl = Decimal('0')
        pnl_ratio = Decimal('0')

        if last_record:
            total_pnl = total_eq_usd - last_record.total_eq
            # 简单日盈亏：当日首笔记录与当前比较
            today_first = NetValueHistory.objects.filter(
                record_time__date=timezone.now().date()
            ).order_by('record_time').first()
            if today_first:
                daily_pnl = total_eq_usd - today_first.total_eq
                pnl_ratio = daily_pnl / today_first.total_eq if today_first.total_eq > 0 else Decimal('0')
        else:
            total_pnl = Decimal('0')

        record = NetValueHistory.objects.create(
            total_eq=total_eq_usd,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            pnl_ratio=pnl_ratio,
        )
        logger.info(f'净值记录: {total_eq_usd} USD, 日盈亏 {daily_pnl}')
        return record
