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
from apps.orders.models import TradeOrder

logger = logging.getLogger(__name__)


class AccountService:
    """账户管理服务"""

    @staticmethod
    def get_balance_from_api(user=None) -> Dict:
        """从 OKX 获取实时余额"""
        client = get_okx_client(user=user)
        result = client.get_account_balance()
        if result['code'] != '0':
            raise Exception(f'获取余额失败: {result.get("msg")}')

        total_eq_usd = Decimal('0')
        details = []
        for item in result.get('data', [])[0].get('details', []):
            eq = Decimal(str(item.get('eq', item.get('cashBal', '0'))))
            avail = Decimal(str(item.get('availEq', item.get('availBal', '0'))))
            frozen = Decimal(str(item.get('frozenBal', '0')))
            # 币种美元价值：OKX 字段为 usdEq / eqUsd；usdPnl 是未实现盈亏(通常为0)，不能用作估值
            usd_val = Decimal(str(item.get('usdEq', item.get('eqUsd', '0'))))
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
    def get_positions_from_api(inst_type: str = '', user=None) -> Dict:
        """从 OKX 获取实时持仓"""
        client = get_okx_client(user=user)
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
                avg_px=AccountService._to_float(item.get('avgPx')),
                mark_px=AccountService._to_float(item.get('markPx')),
                upl=AccountService._to_float(item.get('upl')),
                margin=AccountService._to_float(item.get('margin')),
                leverage=AccountService._to_float(item.get('lever'), 1),
                pos_side=item.get('posSide', 'net'),
                liq_px=AccountService._to_float(item.get('liqPx')),
            )
        return positions

    @staticmethod
    def _to_float(value, default=0.0) -> float:
        """安全转换 OKX 数值字段（空字符串/None/非法值返回默认值）"""
        if value is None or value == '':
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def snapshot_balance(user=None) -> List[BalanceSnapshot]:
        """保存余额快照"""
        balance = AccountService.get_balance_from_api(user=user)
        snapshots = []
        for detail in balance['details']:
            snap = BalanceSnapshot.objects.create(
                user=user if user and user.is_authenticated else None,
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
    def snapshot_positions(inst_type: str = '', user=None) -> List[PositionSnapshot]:
        """保存持仓快照"""
        positions = AccountService.get_positions_from_api(inst_type, user=user)
        snapshots = []
        for pos in positions.values():
            snap = PositionSnapshot.objects.create(
                user=user if user and user.is_authenticated else None,
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
    def record_net_value(user=None) -> NetValueHistory:
        """记录净值"""
        balance = AccountService.get_balance_from_api(user=user)
        total_eq_usd = balance['total_eq_usd']

        last_record = NetValueHistory.objects.filter(
            user=user if user and user.is_authenticated else None
        ).order_by('-record_time').first()
        daily_pnl = Decimal('0')
        pnl_ratio = Decimal('0')

        if last_record:
            total_pnl = total_eq_usd - last_record.total_eq
            # 简单日盈亏：当日首笔记录与当前比较
            today_first = NetValueHistory.objects.filter(
                user=user if user and user.is_authenticated else None,
                record_time__date=timezone.now().date()
            ).order_by('record_time').first()
            if today_first:
                daily_pnl = total_eq_usd - today_first.total_eq
                pnl_ratio = daily_pnl / today_first.total_eq if today_first.total_eq > 0 else Decimal('0')
        else:
            total_pnl = Decimal('0')

        record = NetValueHistory.objects.create(
            user=user if user and user.is_authenticated else None,
            total_eq=total_eq_usd,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            pnl_ratio=pnl_ratio,
        )
        logger.info(f'净值记录: {total_eq_usd} USD, 日盈亏 {daily_pnl}')
        return record

    # ========== 盈亏分析报表 ==========
    @staticmethod
    def pnl_report(user=None, period: str = 'month') -> Dict:
        """盈亏分析报表
        Args:
            period: 'day' | 'week' | 'month' 聚合粒度
        """
        from datetime import timedelta
        from collections import OrderedDict

        qs = NetValueHistory.objects.filter(
            user=user if user and user.is_authenticated else None
        ).order_by('record_time')

        # 时间范围：近90天数据足够聚合
        since = timezone.now() - timedelta(days=90)
        qs = qs.filter(record_time__gte=since)

        records = list(qs)
        if not records:
            return {'period': period, 'items': [], 'summary': {}}

        def _key(dt):
            if period == 'day':
                return dt.strftime('%Y-%m-%d')
            if period == 'week':
                iso = dt.isocalendar()
                return f'{iso[0]}-W{iso[1]:02d}'
            return dt.strftime('%Y-%m')

        # 按期间聚合首尾净值差 = 期间盈亏
        grouped = OrderedDict()
        for r in records:
            key = _key(r.record_time)
            grouped.setdefault(key, {'first': None, 'last': None})
            if grouped[key]['first'] is None or r.record_time < grouped[key]['first']['t']:
                grouped[key]['first'] = {'t': r.record_time, 'eq': float(r.total_eq)}
            if grouped[key]['last'] is None or r.record_time > grouped[key]['last']['t']:
                grouped[key]['last'] = {'t': r.record_time, 'eq': float(r.total_eq)}

        items = []
        prev_last = None
        for key, val in grouped.items():
            pnl = val['last']['eq'] - val['first']['eq']
            # 相对上一个期间的期末净值（若为独立期间则相对自身期初）
            base = prev_last if prev_last is not None else val['first']['eq']
            ratio = (pnl / base * 100) if base else 0
            items.append({
                'period': key,
                'start_eq': round(val['first']['eq'], 4),
                'end_eq': round(val['last']['eq'], 4),
                'pnl': round(pnl, 4),
                'pnl_ratio': round(ratio, 4),
            })
            prev_last = val['last']['eq']

        total_pnl = sum(i['pnl'] for i in items)
        base_eq = items[0]['start_eq'] if items else 0
        summary = {
            'total_pnl': round(total_pnl, 4),
            'total_ratio': round((total_pnl / base_eq * 100), 4) if base_eq else 0,
            'positive_periods': len([i for i in items if i['pnl'] > 0]),
            'total_periods': len(items),
        }
        return {'period': period, 'items': items, 'summary': summary}

    # ========== 手续费统计 ==========
    @staticmethod
    def fee_statistics(user=None, days: int = 30) -> Dict:
        """手续费统计：基于订单记录中的 fee 字段（成交明细）"""
        from collections import OrderedDict

        since = timezone.now() - timedelta(days=days)
        orders = TradeOrder.objects.filter(
            user=user if user and user.is_authenticated else None,
            created_at__gte=since,
        )

        total_fee = 0.0
        by_inst = {}
        daily = OrderedDict()
        for o in orders:
            fee = 0.0
            # 从订单的成交记录或自身 fee 字段统计
            try:
                fills = o.fills or []
                if fills:
                    fee += sum(float(f.get('fee', 0)) for f in fills)
            except (TypeError, ValueError):
                pass
            try:
                if o.fee:
                    fee += float(o.fee)
            except (TypeError, ValueError):
                pass
            if not fee:
                continue
            total_fee += fee
            by_inst[o.inst_id] = round(by_inst.get(o.inst_id, 0) + fee, 6)
            day = o.created_at.strftime('%Y-%m-%d')
            daily[day] = round(daily.get(day, 0) + fee, 6)

        return {
            'days': days,
            'total_fee': round(total_fee, 6),
            'by_inst': dict(sorted(by_inst.items(), key=lambda x: -x[1])),
            'daily': daily,
        }

    # ========== 资金曲线与基准对比 ==========
    @staticmethod
    def equity_vs_benchmark(user=None, days: int = 30) -> Dict:
        """资金曲线与 BTC 基准对比（归一化到100起点）"""
        from apps.market.models import KLine, Instrument

        since = timezone.now() - timedelta(days=days)
        net_values = list(
            NetValueHistory.objects.filter(
                user=user if user and user.is_authenticated else None,
                record_time__gte=since,
            ).order_by('record_time')
        )
        equity = [{'time': r.record_time.isoformat(), 'value': float(r.total_eq)} for r in net_values]
        if not equity:
            return {'equity': [], 'benchmark': [], 'equity_label': '账户净值', 'benchmark_label': 'BTC'}

        base_eq = equity[0]['value'] or 1
        # BTC 1D K线作为基准
        inst = Instrument.objects.filter(inst_id='BTC-USDT').first()
        btc = []
        if inst:
            btc_rows = KLine.objects.filter(
                instrument=inst, bar='1D', environment='demo',
                timestamp__gte=since,
            ).order_by('timestamp')
            btc_klines = list(btc_rows)
            if btc_klines:
                base_close = float(btc_klines[0].close) or 1
                btc = [
                    {'time': k.timestamp.isoformat(), 'value': round(float(k.close) / base_close * 100, 4)}
                    for k in btc_klines
                ]

        # 净值曲线归一化到100
        equity_norm = [
            {'time': e['time'], 'value': round(e['value'] / base_eq * 100, 4)}
            for e in equity
        ]
        return {
            'equity': equity_norm,
            'benchmark': btc,
            'equity_label': '账户净值',
            'benchmark_label': 'BTC',
        }
