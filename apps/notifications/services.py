"""
通知服务层：统一的创建通知入口。
其他模块调用 ``NotificationService.push(**kwargs)`` 创建通知即可，
无需关心 user 过滤 / 重复降噪 / 泛化 Generic FK。
"""
from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from .models import Notification

User = get_user_model()


class NotificationService:
    """通知推送服务。"""

    # 同一类型 + 同一 related_id 的去重窗口（秒），窗口内重复则不产生新通知。
    DEDUP_WINDOW_SEC = {
        Notification.TYPE.MARKET_ALERT: 300,
        Notification.TYPE.RISK_WARNING: 60,
    }

    @classmethod
    def push(cls,
             type: str,
             title: str,
             content: str = '',
             *,
             level: Optional[int] = None,
             user=None,
             target_route: str = '',
             related_object=None,
             related_model: str = '',
             related_id: str = '',
             extra: Optional[dict] = None,
             ) -> Optional[Notification]:
        """
        创建一条通知。

        :param type: Notification.TYPE 之一
        :param title: 标题 (≤120 字)
        :param content: 正文
        :param level: Notification.LEVEL，缺省按 type 推断
        :param user: 接收用户，可为 None（全局模式）
        :param target_route: 前端跳转路径，如 "/orders/detail?id=5"
        :param related_object: 关联 ORM 对象，会填充 content_type/object_id/related_model/related_id
        :param related_model: 关联模型名（无 related_object 时可单独传）
        :param related_id: 关联对象 ID（无 related_object 时可单独传）
        :param extra: 任意 JSON 元数据
        :return: 创建成功返回 Notification，去重命中返回 None
        """
        # 默认 level 推断
        if level is None:
            level = {
                Notification.TYPE.ORDER_STATE: Notification.LEVEL.INFO,
                Notification.TYPE.SIGNAL_GENERATED: Notification.LEVEL.SUCCESS,
                Notification.TYPE.RISK_WARNING: Notification.LEVEL.WARNING,
                Notification.TYPE.STRATEGY_EVENT: Notification.LEVEL.INFO,
                Notification.TYPE.BACKTEST_DONE: Notification.LEVEL.SUCCESS,
                Notification.TYPE.SYSTEM_NOTICE: Notification.LEVEL.INFO,
                Notification.TYPE.MARKET_ALERT: Notification.LEVEL.WARNING,
            }.get(type, Notification.LEVEL.INFO)

        # 处理关联对象
        ct = None
        obj_id = ''
        if related_object is not None:
            ct = ContentType.objects.get_for_model(related_object)
            obj_id = str(related_object.pk)
            if not related_model:
                related_model = related_object.__class__.__name__
            if not related_id:
                related_id = obj_id

        # 去重
        dedup_window = cls.DEDUP_WINDOW_SEC.get(type, 0)
        if dedup_window > 0:
            from django.utils import timezone
            threshold = timezone.now() - timezone.timedelta(seconds=dedup_window)
            qs = Notification.objects.filter(
                type=type, user=user, related_model=related_model, related_id=related_id,
                created_at__gte=threshold,
            )
            if qs.exists():
                return None

        return Notification.objects.create(
            user=user,
            type=type,
            level=level,
            title=title[:120],
            content=content,
            target_route=target_route,
            related_model=related_model,
            related_id=related_id,
            content_type=ct,
            object_id=obj_id,
            extra=extra or {},
        )

    # -------- 便捷构造 --------
    @classmethod
    def from_order_state(cls, order, prev_state: str, *, user=None) -> Optional[Notification]:
        """订单状态变更推送。"""
        from apps.orders.models import TradeOrder
        state_map = {
            TradeOrder.STATE.FILLED: (Notification.LEVEL.SUCCESS, '订单已成交',
                                       f'订单 #{order.id} ({order.inst_id}) 已全部成交，成交价 {order.fill_px or order.px}'),
            TradeOrder.STATE.CANCELED: (Notification.LEVEL.INFO, '订单已撤销',
                                         f'订单 #{order.id} ({order.inst_id}) 已撤销'),
            TradeOrder.STATE.REJECTED: (Notification.LEVEL.DANGER, '订单被拒绝',
                                         f'订单 #{order.id} ({order.inst_id}) 被交易所拒绝：{order.error_msg or "未知原因"}'),
            TradeOrder.STATE.LIVE: (Notification.LEVEL.INFO, '订单挂出',
                                     f'订单 #{order.id} ({order.inst_id}) 已进入挂单队列，单号 {order.ord_id or "-"}'),
            TradeOrder.STATE.PARTIALLY_FILLED: (Notification.LEVEL.SUCCESS, '订单部分成交',
                                                  f'订单 #{order.id} ({order.inst_id}) 部分成交，进度 {order.fill_sz}/{order.sz}'),
        }
        info = state_map.get(order.state)
        if not info:
            return None
        level, title, content = info
        if prev_state == order.state:
            return None
        return cls.push(
            Notification.TYPE.ORDER_STATE, title, content,
            level=level, user=user, related_object=order,
            target_route=f'/orders?tab=normal&detail={order.id}',
        )

    @classmethod
    def from_signal(cls, signal, *, user=None) -> Optional[Notification]:
        """策略信号生成推送。"""
        action = signal.get_action_display() if hasattr(signal, 'get_action_display') else signal.action
        score = getattr(signal, 'score', '')
        score_txt = f' (评分 {float(score):.2f})' if score not in (None, '', 0) else ''
        return cls.push(
            Notification.TYPE.SIGNAL_GENERATED,
            f'策略信号：{action} {signal.inst_id}',
            f'策略 #{signal.strategy_id} 在 {signal.inst_id} 触发 {action} 信号{score_txt}',
            level=Notification.LEVEL.SUCCESS if signal.action in ('buy', 'sell') else Notification.LEVEL.INFO,
            user=user, related_object=signal,
            target_route=f'/strategy/signals?id={signal.id}',
        )

    @classmethod
    def from_risk(cls, *, title: str, reason: str, order=None, strategy=None,
                  user=None, extra=None) -> Optional[Notification]:
        """风控触发推送。"""
        return cls.push(
            Notification.TYPE.RISK_WARNING, title or '风控拦截', reason,
            level=Notification.LEVEL.WARNING,
            user=user, related_object=order,
            related_model=strategy.__class__.__name__ if strategy else '',
            related_id=str(getattr(strategy, 'pk', '')),
            target_route='/orders' if order else '/strategy',
            extra=extra,
        )
