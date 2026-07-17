"""
账户模型：余额快照、持仓快照、净值历史、OKX凭证
"""

from django.db import models
from django.utils import timezone


class BalanceSnapshot(models.Model):
    """账户余额快照"""

    ccy = models.CharField('币种', max_length=20)
    total_eq = models.DecimalField('总权益', max_digits=24, decimal_places=8)
    avail_eq = models.DecimalField('可用余额', max_digits=24, decimal_places=8)
    frozen_bal = models.DecimalField('冻结余额', max_digits=24, decimal_places=8, default=0)
    usd_value = models.DecimalField('USD价值', max_digits=24, decimal_places=4, null=True)
    discount = models.DecimalField('折算率', max_digits=8, decimal_places=4, default=1)
    snapshot_time = models.DateTimeField('快照时间', default=timezone.now, db_index=True)

    class Meta:
        db_table = 'account_balance_snapshot'
        verbose_name = '余额快照'
        verbose_name_plural = verbose_name
        ordering = ['-snapshot_time', 'ccy']

    def __str__(self):
        return f'{self.ccy}: {self.total_eq} @ {self.snapshot_time}'


class PositionSnapshot(models.Model):
    """持仓快照"""

    POS_SIDE_CHOICES = [
        ('long', '多头'),
        ('short', '空头'),
    ]

    inst_id = models.CharField('产品ID', max_length=50)
    inst_type = models.CharField('产品类型', max_length=20)
    pos_side = models.CharField('持仓方向', max_length=10, choices=POS_SIDE_CHOICES)
    pos = models.DecimalField('持仓数量', max_digits=24, decimal_places=8)
    avg_px = models.DecimalField('开仓均价', max_digits=24, decimal_places=8)
    mark_px = models.DecimalField('标记价格', max_digits=24, decimal_places=8)
    liq_px = models.DecimalField('强平价', max_digits=24, decimal_places=8, null=True)
    upl = models.DecimalField('未实现盈亏', max_digits=24, decimal_places=8)
    margin = models.DecimalField('保证金', max_digits=24, decimal_places=8)
    mgn_ratio = models.DecimalField('保证金率', max_digits=8, decimal_places=4, null=True)
    leverage = models.DecimalField('杠杆倍数', max_digits=8, decimal_places=2)
    snapshot_time = models.DateTimeField('快照时间', default=timezone.now, db_index=True)

    class Meta:
        db_table = 'account_position_snapshot'
        verbose_name = '持仓快照'
        verbose_name_plural = verbose_name
        ordering = ['-snapshot_time']

    def __str__(self):
        return f'{self.inst_id} {self.pos_side} {self.pos}'


class NetValueHistory(models.Model):
    """净值历史"""

    total_eq = models.DecimalField('总权益', max_digits=24, decimal_places=8)
    total_pnl = models.DecimalField('总盈亏', max_digits=24, decimal_places=8, default=0)
    daily_pnl = models.DecimalField('日盈亏', max_digits=24, decimal_places=8, default=0)
    pnl_ratio = models.DecimalField('收益率', max_digits=8, decimal_places=6, default=0)
    record_time = models.DateTimeField('记录时间', default=timezone.now, db_index=True)

    class Meta:
        db_table = 'account_net_value'
        verbose_name = '净值历史'
        verbose_name_plural = verbose_name
        ordering = ['-record_time']

    def __str__(self):
        return f'NetValue: {self.total_eq} ({self.pnl_ratio:.4%}) @ {self.record_time}'


class OKXCredential(models.Model):
    """OKX API 凭证（按环境分别存储：demo / live）"""

    FLAG_CHOICES = [
        ('0', '实盘 (Live)'),
        ('1', '模拟盘 (Demo)'),
    ]

    ENV_CHOICES = [
        ('demo', '模拟盘'),
        ('live', '实盘'),
    ]

    name = models.CharField('环境', max_length=20, choices=ENV_CHOICES, default='demo', unique=True)
    api_key = models.CharField('API Key', max_length=200)
    api_secret = models.CharField('Secret Key', max_length=200)
    passphrase = models.CharField('Passphrase', max_length=200)
    flag = models.CharField('交易模式', max_length=1, choices=FLAG_CHOICES, default='1')
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'account_okx_credential'
        verbose_name = 'OKX凭证'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.get_name_display()} ({self.get_flag_display()})'


class SystemConfig(models.Model):
    """系统全局配置（单例）"""

    ENV_CHOICES = [
        ('demo', '模拟盘'),
        ('live', '实盘'),
    ]

    active_environment = models.CharField('当前交易环境', max_length=10, choices=ENV_CHOICES, default='demo')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'account_system_config'
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config


