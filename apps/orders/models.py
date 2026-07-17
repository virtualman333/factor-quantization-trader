"""
订单模型：交易订单记录
"""

from django.db import models


class TradeOrder(models.Model):
    """交易订单"""

    ORD_TYPE_CHOICES = [
        ('market', '市价单'),
        ('limit', '限价单'),
        ('post_only', '只做maker'),
        ('fok', '全部成交或立即取消'),
        ('ioc', '立即成交并取消剩余'),
    ]

    SIDE_CHOICES = [
        ('buy', '买入'),
        ('sell', '卖出'),
    ]

    STATE_CHOICES = [
        ('live', '等待成交'),
        ('partially_filled', '部分成交'),
        ('filled', '完全成交'),
        ('canceled', '已撤销'),
        ('failed', '失败'),
    ]

    ord_id = models.CharField('订单ID', max_length=64, blank=True, db_index=True)
    cl_ord_id = models.CharField('客户自定义订单ID', max_length=64, blank=True)
    inst_id = models.CharField('产品ID', max_length=50, db_index=True)
    td_mode = models.CharField('交易模式', max_length=20, default='cash')  # cash / cross / isolated
    side = models.CharField('买卖方向', max_length=10, choices=SIDE_CHOICES)
    ord_type = models.CharField('订单类型', max_length=20, choices=ORD_TYPE_CHOICES)
    sz = models.DecimalField('委托数量', max_digits=24, decimal_places=8)
    px = models.DecimalField('委托价格', max_digits=24, decimal_places=8, null=True, blank=True)
    fill_sz = models.DecimalField('成交数量', max_digits=24, decimal_places=8, default=0)
    fill_px = models.DecimalField('成交均价', max_digits=24, decimal_places=8, null=True, blank=True)
    fee = models.DecimalField('手续费', max_digits=24, decimal_places=8, default=0)
    fee_ccy = models.CharField('手续费币种', max_length=20, blank=True)
    state = models.CharField('订单状态', max_length=20, choices=STATE_CHOICES, default='live')
    pnl = models.DecimalField('盈亏(平仓时)', max_digits=24, decimal_places=8, null=True, blank=True)
    source = models.CharField('来源', max_length=50, default='manual',
                               help_text='来源: manual / strategy / signal')
    strategy_id = models.IntegerField('关联策略ID', null=True, blank=True)
    signal_id = models.IntegerField('关联信号ID', null=True, blank=True)

    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    filled_at = models.DateTimeField('成交时间', null=True, blank=True)

    class Meta:
        db_table = 'trade_order'
        verbose_name = '交易订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['inst_id', 'state']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.ord_id or self.cl_ord_id} {self.side} {self.inst_id} {self.sz} @ {self.px or "MKT"} ({self.get_state_display()})'


class OrderLog(models.Model):
    """订单操作日志"""

    ACTION_CHOICES = [
        ('created', '创建'),
        ('submitted', '已提交'),
        ('filled', '成交'),
        ('partial_fill', '部分成交'),
        ('canceled', '撤销'),
        ('amended', '修改'),
        ('failed', '失败'),
        ('error', '错误'),
    ]

    order = models.ForeignKey(TradeOrder, on_delete=models.CASCADE,
                               related_name='logs', verbose_name='关联订单')
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    detail = models.JSONField('详细信息', default=dict)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        db_table = 'trade_order_log'
        verbose_name = '订单日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order} | {self.get_action_display()}'
