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
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def _safe_notify_order(order, prev_state: str, user=None):
    """订单状态变更通知推送（失败不影响主流程）。"""
    try:
        NotificationService.from_order_state(order, prev_state=prev_state, user=user)
    except Exception as exc:  # pragma: no cover - 防御性
        logger.warning(f'推送订单状态通知失败: {exc}', exc_info=False)


def _safe_notify_risk(title: str, reason: str, *, order=None, strategy=None,
                      user=None, extra=None):
    """风控告警通知（失败不影响主流程）。"""
    try:
        NotificationService.from_risk(title=title, reason=reason, order=order,
                                       strategy=strategy, user=user, extra=extra)
    except Exception as exc:  # pragma: no cover - 防御性
        logger.warning(f'推送风控通知失败: {exc}', exc_info=False)


class OrderService:
    """订单管理服务"""

    @staticmethod
    def _normalize_int(value):
        """整型字段归一化：空串/None/0 -> None；合法数字转 int，非法抛 ValueError"""
        if value is None or value == '' or value == 0:
            return None
        # 允许字符串或数字
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        if n <= 0:
            return None
        return n

    @staticmethod
    def create_order(inst_id: str, side: str, ord_type: str, sz: str,
                     px: str = '', td_mode: str = 'cash',
                     pos_side: str = '', leverage: float = 1,
                     source: str = 'manual',
                     strategy_id=None, signal_id=None,
                     user=None) -> Dict:
        """创建并提交订单（支持合约杠杆）"""
        # 类型归一化：把 strategy_id / signal_id 的空字符串 / None 统一为 None，避免 IntegerField 报错
        strategy_id = OrderService._normalize_int(strategy_id)
        signal_id = OrderService._normalize_int(signal_id)
        user_id = user.id if user and user.is_authenticated else 0
        risk_mgr = RiskManager(user_id=user_id)
        order_value = float(sz) * (float(px) if px else 0)
        client = get_okx_client(user=user)
        # 下单前检查凭证：未配置则给出友好中文提示，而不是裸抛 OKX 错误
        client.require_credentials('下单')

        if ord_type == 'market' and not px:
            ticker = client.get_ticker(inst_id)
            if ticker['code'] == '0' and ticker['data']:
                order_value = float(sz) * float(ticker['data'][0]['last'])

        if order_value > 0:
            try:
                risk_mgr.pre_order_check(
                    inst_id=inst_id, side=side, sz=float(sz),
                    px=float(px or 0), account_balance=float('inf'),
                    current_positions={},
                )
            except OrderRejectedError as exc:
                _safe_notify_risk(
                    '下单被风控拦截', str(exc), user=user,
                    extra={'inst_id': inst_id, 'side': side, 'sz': sz, 'px': px},
                )
                raise

        # 现货风控：不能没仓位就卖；只有合约才可以做空
        is_spot = (td_mode or '').lower() == 'cash'
        if is_spot and side.lower() == 'sell':
            # 现货卖出必须有对应持仓（数量足够才可卖）
            from apps.strategy.services import StrategyService
            # 复用持仓查询：现货余额即持仓
            spot_pos = None
            try:
                balance = client.get_account_balance()
                if balance.get('code') == '0':
                    base_ccy = inst_id.split('-')[0] if '-' in inst_id else inst_id
                    details = balance.get('data', [{}])[0].get('details', [])
                    coin = next((d for d in details if d.get('ccy') == base_ccy), None)
                    if coin:
                        free = float(coin.get('availEq', coin.get('cashBal', 0)) or 0)
                        if free > 0:
                            spot_pos = free
            except Exception:
                spot_pos = None
            if not spot_pos:
                raise OrderRejectedError(f'现货 {inst_id} 无持仓，不能卖出')
            # 卖出数量不能超过可用持仓
            try:
                sz_num = float(sz)
                if sz_num > spot_pos:
                    raise OrderRejectedError(
                        f'卖出数量 {sz_num} 超过现货持仓 {spot_pos}')
            except ValueError:
                pass
            pos_side = ''  # 现货不传 posSide

        # 合约模式下设置杠杆
        if td_mode in ('cross', 'isolated') and leverage > 1:
            try:
                client.set_leverage(
                    lever=str(int(leverage)),
                    mgn_mode=td_mode,
                    inst_id=inst_id,
                )
            except Exception as e:
                logger.warning(f'设置杠杆失败（可能已设置）: {e}')

        # 现货市价买单：OKX 要求 sz 以计价币(quote)金额为单位（tgtCcy=quote_ccy），
        # 否则按 base 数量会报 51020 "minimum order amount"。
        # 这里把用户输入的币数量（如 0.01 BTC）按现价换算成计价币金额。
        tgt_ccy = ''
        submit_sz = sz
        if is_spot and side.lower() == 'buy' and ord_type == 'market':
            try:
                ticker = client.get_ticker(inst_id)
                if ticker.get('code') == '0' and ticker.get('data'):
                    last = float(ticker['data'][0]['last'])
                    sz_num = float(sz)
                    if last > 0 and sz_num > 0:
                        submit_sz = str(round(sz_num * last, 6))
                        tgt_ccy = 'quote_ccy'
            except Exception as e:
                logger.warning(f'现货市价买单换算金额失败，回退原始数量: {e}')

        # 生成客户订单ID
        cl_ord_id = f'qt_{uuid.uuid4().hex[:12]}'

        # 创建本地订单记录（sz 保存用户原始输入，实际提交用 submit_sz）
        trade_order = TradeOrder.objects.create(
            user=user if user and user.is_authenticated else None,
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
                                 detail={'cl_ord_id': cl_ord_id, 'leverage': leverage})

        # 提交到 OKX
        # 现货订单不传 clOrdId：OKX 现货对 clOrdId 校验严格（卖单常报 51000），
        # 由 OKX 自动生成，本地仍保留 cl_ord_id 作为内部标识。
        submit_cl_oid = '' if is_spot else cl_ord_id
        result = client.place_order(
            inst_id=inst_id, td_mode=td_mode, side=side,
            ord_type=ord_type, sz=submit_sz, px=px,
            pos_side=pos_side, tgt_ccy=tgt_ccy, client_oid=submit_cl_oid,
        )


        if result['code'] == '0':
            data = result.get('data', [{}])[0]
            trade_order.ord_id = data.get('ordId', '')
            trade_order.state = 'live'
            trade_order.save()
            OrderLog.objects.create(order=trade_order, action='submitted',
                                     detail={'ord_id': trade_order.ord_id, 'result': result})
            # 订单挂出成功通知（状态 live 没变，显式推送 submitted）
            try:
                NotificationService.push(
                    Notification.TYPE.ORDER_STATE,
                    '订单已挂出',
                    f'订单 #{trade_order.id} ({trade_order.inst_id}) 已提交到交易所，单号 {trade_order.ord_id or "-"}',
                    level=Notification.LEVEL.INFO, user=user,
                    related_object=trade_order,
                    target_route=f'/orders?tab=normal&detail={trade_order.id}',
                )
            except Exception:  # pragma: no cover
                pass
            logger.info(f'订单提交成功: {trade_order.ord_id}')
        else:
            prev = trade_order.state
            trade_order.state = 'failed'
            trade_order.save()
            OrderLog.objects.create(order=trade_order, action='failed',
                                     detail={'error': result.get('msg')})
            _safe_notify_order(trade_order, prev_state=prev, user=user)
            raise OrderRejectedError(f'Order rejected: {result.get("msg")}')

        return {
            'ord_id': trade_order.ord_id,
            'cl_ord_id': trade_order.cl_ord_id,
            'state': trade_order.state,
            'result': result,
        }

    @staticmethod
    def cancel_order(ord_id: str, inst_id: str = '', user=None) -> Dict:
        """撤销订单"""
        client = get_okx_client(user=user)
        client.require_credentials('撤单')

        # 查找本地订单
        trade_order = TradeOrder.objects.filter(
            ord_id=ord_id, state__in=['live', 'partially_filled']
        ).first()

        if not trade_order:
            raise OrderRejectedError(f'未找到活跃订单: {ord_id}')

        inst_id = inst_id or trade_order.inst_id

        # 双向持仓模式下撤单必须携带 posSide（long/short）：
        # 先从 OKX 查询订单持仓方向，查询失败则按无持仓方向撤单
        pos_side = ''
        try:
            info = client.get_order(inst_id=inst_id, ord_id=ord_id)
            data = (info.get('data') or [{}])[0]
            candidate = data.get('posSide', '') or ''
            if candidate in ('long', 'short'):
                pos_side = candidate
        except Exception as e:
            logger.warning(f'查询订单 {ord_id} posSide 失败: {e}')

        result = client.cancel_order(
            inst_id=inst_id, ord_id=ord_id, pos_side=pos_side
        )

        if result['code'] == '0':
            prev_state = trade_order.state
            trade_order.state = 'canceled'
            trade_order.save()
            OrderLog.objects.create(
                order=trade_order, action='canceled',
                detail={'ord_id': ord_id, 'result': result}
            )
            _safe_notify_order(trade_order, prev_state=prev_state, user=user)
            logger.info(f'订单撤单成功: {ord_id}')

        return {'ord_id': ord_id, 'state': trade_order.state, 'result': result}

    @staticmethod
    def sync_order_status(ord_id: str, user=None) -> Optional[TradeOrder]:
        """同步单个订单状态"""
        trade_order = TradeOrder.objects.filter(ord_id=ord_id).first()
        if not trade_order:
            logger.warning(f'未找到本地订单: {ord_id}')
            return None

        client = get_okx_client(user=user)
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
            _safe_notify_order(trade_order, prev_state=old_state, user=user)
            logger.info(f'订单 {ord_id} 状态变更: {old_state} -> {new_state}')

        return trade_order

    @staticmethod
    def sync_pending_orders(user=None) -> int:
        """同步所有待处理订单状态"""
        pending = TradeOrder.objects.filter(
            state__in=['live', 'partially_filled']
        )
        count = 0
        for order in pending:
            try:
                OrderService.sync_order_status(order.ord_id, user=user)
                count += 1
            except Exception as e:
                logger.error(f'同步订单 {order.ord_id} 失败: {e}')
        return count

    @staticmethod
    def place_algo(inst_id: str, side: str, sz: str, td_mode: str = 'cash',
                   ord_type: str = 'conditional', trigger_px: str = '',
                   px: str = '', tp_trigger_px: str = '', tp_order_px: str = '',
                   sl_trigger_px: str = '', sl_order_px: str = '',
                   source: str = 'algo', user=None) -> dict:
        """条件单/止盈止损单（OKX Algo 交易）"""
        from core.okx_client import get_okx_client
        from apps.account.models import OKXCredential

        client = get_okx_client(user=user)
        client.require_credentials('条件单')
        env = OKXCredential.objects.filter(user=user).first()
        td = td_mode or (env.name if env else 'cash')

        result = client.place_algo_order(
            inst_id=inst_id, td_mode=td, side=side, sz=str(sz),
            ord_type=ord_type, trigger_px=str(trigger_px) if trigger_px else '',
            px=str(px) if px else '',
            tp_trigger_px=str(tp_trigger_px) if tp_trigger_px else '',
            tp_order_px=str(tp_order_px) if tp_order_px else '',
            sl_trigger_px=str(sl_trigger_px) if sl_trigger_px else '',
            sl_order_px=str(sl_order_px) if sl_order_px else '',
        )
        return {'result': result, 'type': 'algo'}

    @staticmethod
    def place_twap(inst_id: str, side: str, total_sz: str, slices: int = 5,
                   interval: int = 60, td_mode: str = 'cash', user=None) -> dict:
        """TWAP 时间加权算法单：拆分为 N 个子单按时间间隔下单"""
        from core.okx_client import get_okx_client
        from apps.account.models import OKXCredential

        total = float(total_sz)
        if total <= 0 or slices <= 0:
            raise ValueError('数量或切片数必须大于0')

        client = get_okx_client(user=user)
        client.require_credentials('TWAP算法单')
        env = OKXCredential.objects.filter(user=user).first()
        td = td_mode or (env.name if env else 'cash')
        per_slice = round(total / slices, 8)

        result = client.place_order(inst_id=inst_id, td_mode=td, side=side,
                                    sz=str(per_slice), ord_type='market', px='')
        for i in range(1, slices):
            OrderLog.objects.create(
                user=user,
                order=None,
                action='twap_scheduled',
                detail={
                    'inst_id': inst_id, 'side': side, 'sz': str(per_slice),
                    'interval': interval, 'slot': i,
                },
            )
        return {
            'result': result,
            'type': 'twap',
            'total_slices': slices,
            'per_slice': per_slice,
            'interval_seconds': interval,
            'scheduled_logs': slices - 1,
        }

    @staticmethod
    def place_iceberg(inst_id: str, side: str, total_sz: str, display_sz: str,
                      slices: int = 5, px: str = '', td_mode: str = 'cash',
                      user=None) -> dict:
        """冰山算法单：每次只暴露部分数量"""
        from core.okx_client import get_okx_client
        from apps.account.models import OKXCredential

        total = float(total_sz)
        if total <= 0 or slices <= 0:
            raise ValueError('数量或切片数必须大于0')

        client = get_okx_client(user=user)
        client.require_credentials('冰山算法单')
        env = OKXCredential.objects.filter(user=user).first()
        td = td_mode or (env.name if env else 'cash')
        per_slice = round(total / slices, 8)

        result = client.place_order(inst_id=inst_id, td_mode=td, side=side,
                                    sz=str(per_slice), ord_type='limit' if px else 'market',
                                    px=px)
        for i in range(1, slices):
            OrderLog.objects.create(
                user=user,
                order=None,
                action='iceberg_scheduled',
                detail={
                    'inst_id': inst_id, 'side': side, 'sz': str(per_slice),
                    'px': px, 'slot': i,
                },
            )
        return {
            'result': result,
            'type': 'iceberg',
            'total_slices': slices,
            'per_slice': per_slice,
            'display_sz': display_sz,
        }

    @staticmethod
    def place_market_close(inst_id: str, sz: str, side: str = '',
                           td_mode: str = 'cash', source: str = 'strategy',
                           user=None) -> Dict:
        """市价平仓"""
        if not side:
            from apps.account.services import AccountService
            positions = AccountService.get_positions_from_api(user=user)
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
            user=user,
        )

    @staticmethod
    def list_algo_orders(algo_type: str = 'conditional',
                         inst_type: str = '', inst_id: str = '',
                         include_history: bool = False,
                         user=None) -> dict:
        """条件单/算法单列表查询。
        algo_type: conditional / oco / tp_sl / twap / iceberg
        - conditional/oco/tp_sl: 直接从 OKX 查 algos_pending (algoType=1,2,3)
        - twap/iceberg: 从本地 TradeOrder 表查 (source=twap/iceberg) 并按批次聚合
        """
        from core.okx_client import get_okx_client
        from apps.orders.models import TradeOrder
        from django.db.models import Q, Count, Sum

        algo_type = (algo_type or 'conditional').lower()
        okx_mapping = {
            'conditional': '1',
            'oco': '2',
            'tp_sl': '3',
            '1': '1', '2': '2', '3': '3',
        }

        if algo_type in okx_mapping:
            # 走 OKX 条件单原生接口
            client = get_okx_client(user=user)
            client.require_credentials('查询条件单')
            pending = client.get_algos_pending(
                algo_type=okx_mapping[algo_type],
                inst_type=inst_type or 'SWAP',
                inst_id=inst_id,
                limit=100,
            ) or {}
            items = pending.get('data', []) if isinstance(pending, dict) else []
            history = []
            if include_history:
                hist = client.get_algos_history(
                    algo_type=okx_mapping[algo_type],
                    inst_type=inst_type or 'SWAP',
                    inst_id=inst_id,
                    limit=100,
                ) or {}
                history = hist.get('data', []) if isinstance(hist, dict) else []
            return {
                'type': algo_type,
                'backend': 'okx',
                'results': items,
                'count': len(items),
                'history': history,
                'history_count': len(history),
            }

        if algo_type in ('twap', 'iceberg'):
            qs = TradeOrder.objects.filter(user=user, source=algo_type).order_by('-created_at')
            if inst_id:
                qs = qs.filter(inst_id=inst_id)
            state_live = ['live', 'partially_filled']
            if not include_history:
                qs = qs.filter(state__in=state_live)
            qs = qs[:200]
            items = list(qs.values(
                'id', 'inst_id', 'side', 'ord_type', 'sz', 'px', 'fill_sz',
                'state', 'strategy_id', 'created_at', 'updated_at'
            ))
            # 按 created_at 近似聚合批次（同一分钟内创建的同方向同品种视为一批）
            batches = {}
            for it in items:
                key = (it['inst_id'], it['side'], it['created_at'].strftime('%Y%m%d%H%M'))
                b = batches.setdefault(key, {
                    'batch_id': f"{it['inst_id']}_{it['side']}_{key[2]}",
                    'inst_id': it['inst_id'],
                    'side': it['side'],
                    'created_at': it['created_at'],
                    'total_slices': 0,
                    'filled_slices': 0,
                    'pending_slices': 0,
                    'total_sz': 0,
                    'fill_sz': 0,
                    'progress': 0.0,
                    'details': [],
                })
                b['total_slices'] += 1
                sz = float(it['sz'] or 0)
                fill_sz = float(it['fill_sz'] or 0)
                b['total_sz'] += sz
                b['fill_sz'] += fill_sz
                if it['state'] in ('filled',):
                    b['filled_slices'] += 1
                elif it['state'] in ('live', 'partially_filled'):
                    b['pending_slices'] += 1
                b['details'].append(it)
            for b in batches.values():
                if b['total_slices']:
                    b['progress'] = round(b['filled_slices'] / b['total_slices'], 4)
                b['total_sz'] = f"{b['total_sz']:.6g}"
                b['fill_sz'] = f"{b['fill_sz']:.6g}"
            return {
                'type': algo_type,
                'backend': 'local',
                'results': list(batches.values()),
                'count': len(batches),
                'details': items,
                'details_count': len(items),
            }

        return {'type': algo_type, 'results': [], 'count': 0}

    @staticmethod
    def cancel_algo(algo_type: str, inst_id: str, algo_id: str = '',
                    ids: list = None, user=None) -> dict:
        """取消条件单/算法单
        - OKX 条件单：需要 [{instId, algoId}] 单次 1-10 个
        - 本地 TWAP/冰山：批量取消 state in [live, partially_filled] 的订单
        """
        from core.okx_client import get_okx_client
        from apps.orders.models import TradeOrder

        algo_type = (algo_type or 'conditional').lower()
        if algo_type in ('conditional', 'oco', 'tp_sl', '1', '2', '3'):
            client = get_okx_client(user=user)
            client.require_credentials('撤销条件单')
            batch = ids or [{'instId': inst_id, 'algoId': algo_id}]
            res = client.cancel_algos(batch) or {}
            return {'backend': 'okx', 'result': res}

        if algo_type in ('twap', 'iceberg'):
            qs = TradeOrder.objects.filter(
                user=user, source=algo_type, state__in=['live', 'partially_filled'],
            )
            if inst_id:
                qs = qs.filter(inst_id=inst_id)
            # 如果传的是本地订单 ids 列表，只取消这些
            if ids and len(ids):
                qs = qs.filter(id__in=ids)
            canceled = 0
            errors = []
            for o in qs:
                try:
                    OrderService.cancel_order(ord_id=o.ord_id, inst_id=o.inst_id, user=user)
                    canceled += 1
                except Exception as e:
                    errors.append({'id': o.id, 'error': str(e)})
            return {
                'backend': 'local',
                'canceled': canceled,
                'errors': errors,
            }

        return {'error': f'不支持的 algo_type: {algo_type}'}
