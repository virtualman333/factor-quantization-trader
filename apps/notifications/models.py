"""
消息通知模型。

策略：
- 本项目默认单用户运行，user 可为空（AllowAny 模式下全局共享通知流）。
- 支持多用户部署时：把 user 非空即可，API 层按 request.user 自动过滤。
- 7 种业务通知类型：order_state / signal_generated / risk_warning /
  strategy_event / backtest_done / system_notice / market_alert
- 相关对象通过 content_object GenericForeignKey 或元组 (related_app, related_model, related_id) 引用。
"""
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    class LEVEL(models.IntegerChoices):
        INFO = 10, 'info'
        SUCCESS = 20, 'success'
        WARNING = 30, 'warning'
        DANGER = 40, 'danger'

    class TYPE(models.TextChoices):
        ORDER_STATE = 'order_state', '订单状态更新'
        SIGNAL_GENERATED = 'signal_generated', '策略信号'
        RISK_WARNING = 'risk_warning', '风控告警'
        STRATEGY_EVENT = 'strategy_event', '策略事件'
        BACKTEST_DONE = 'backtest_done', '回测完成'
        SYSTEM_NOTICE = 'system_notice', '系统公告'
        MARKET_ALERT = 'market_alert', '行情异动'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications',
                             null=True, blank=True,
                             help_text='空=全局/单用户模式下所有用户可见')
    type = models.CharField(max_length=32, choices=TYPE.choices, default=TYPE.SYSTEM_NOTICE)
    level = models.IntegerField(choices=LEVEL.choices, default=LEVEL.INFO)
    title = models.CharField(max_length=120)
    content = models.TextField(blank=True, default='')
    read = models.BooleanField(default=False, db_index=True)
    # 跳转锚点：前端收到后可用它打开对应页面（如 /orders/detail?id=xxx）
    target_route = models.CharField(max_length=200, blank=True, default='',
                                    help_text='如 /orders?tab=normal / /strategy/signals?id=123')
    # 关联对象的便捷字段（无 Generic FK 时也可用）
    related_model = models.CharField(max_length=64, blank=True, default='',
                                     help_text='如 TradeOrder / SignalRecord / BacktestResult')
    related_id = models.CharField(max_length=64, blank=True, default='')

    # Generic FK（可选，便于 ORM 反查）
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL,
                                     null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True, default='')
    content_object = GenericForeignKey('content_type', 'object_id')

    # 元数据：任意 JSON
    extra = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read']),
            models.Index(fields=['type', 'created_at']),
        ]

    def __str__(self):
        return f'[{self.get_type_display()}] {self.title}'
