"""
账户模型：余额快照、持仓快照、净值历史、OKX凭证
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class BalanceSnapshot(models.Model):
    """账户余额快照"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='balance_snapshots', verbose_name='所属用户',
                              null=True, default=None)
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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='position_snapshots', verbose_name='所属用户',
                              null=True, default=None)
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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='net_value_history', verbose_name='所属用户',
                              null=True, default=None)
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
    """OKX API 凭证（按用户+环境分别存储：demo / live）"""

    FLAG_CHOICES = [
        ('0', '实盘 (Live)'),
        ('1', '模拟盘 (Demo)'),
    ]

    ENV_CHOICES = [
        ('demo', '模拟盘'),
        ('live', '实盘'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='okx_credentials', verbose_name='所属用户',
                              null=True, default=None)
    name = models.CharField('环境', max_length=20, choices=ENV_CHOICES, default='demo')
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
        unique_together = [('user', 'name')]

    def __str__(self):
        return f'[{self.user}] {self.get_name_display()} ({self.get_flag_display()})'


class SystemConfig(models.Model):
    """系统全局配置（按用户隔离，每个用户独立环境选择）"""

    ENV_CHOICES = [
        ('demo', '模拟盘'),
        ('live', '实盘'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='system_config', verbose_name='所属用户',
                                 null=True, default=None)
    active_environment = models.CharField('当前交易环境', max_length=10, choices=ENV_CHOICES, default='demo')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'account_system_config'
        verbose_name = '系统配置'
        verbose_name_plural = verbose_name

    @classmethod
    def get_config(cls, user=None):
        if user and user.is_authenticated:
            config, _ = cls.objects.get_or_create(user=user, defaults={'active_environment': 'demo'})
        else:
            config, _ = cls.objects.get_or_create(user_id=1, defaults={'active_environment': 'demo'})
        return config


class UserQuota(models.Model):
    """用户配额管理"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='quota', verbose_name='所属用户')
    max_strategies = models.PositiveIntegerField('最大策略数', default=10)
    max_orders_per_day = models.PositiveIntegerField('每日最大下单次数', default=100)
    max_api_calls_per_minute = models.PositiveIntegerField('每分钟最大API调用次数', default=60)
    max_klines_per_request = models.PositiveIntegerField('单次K线查询上限', default=500)
    is_trading_enabled = models.BooleanField('允许交易', default=True)
    is_data_sync_enabled = models.BooleanField('允许数据同步', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'account_user_quota'
        verbose_name = '用户配额'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.user.username} 配额'

    @classmethod
    def get_quota(cls, user):
        quota, _ = cls.objects.get_or_create(user=user)
        return quota


class GlobalConfig(models.Model):
    """系统级全局配置（仅管理员可修改，对所有用户生效）"""

    id = models.PositiveIntegerField('配置ID', primary_key=True, default=1)
    # 市场数据同步
    market_sync_interval = models.PositiveIntegerField('行情同步间隔(秒)', default=60)
    market_sync_instruments = models.BooleanField('同步交易品种', default=True)
    market_sync_tickers = models.BooleanField('同步行情快照', default=True)
    market_sync_klines = models.BooleanField('同步K线数据', default=True)
    max_tickers_sync_count = models.PositiveIntegerField('行情快照最大同步品种数', default=50)
    # 全局风控
    global_max_position_pct = models.DecimalField('全局最大持仓比例', max_digits=5, decimal_places=4, default=0.2)
    global_max_order_value = models.DecimalField('全局最大订单价值(USD)', max_digits=14, decimal_places=2, default=10000)
    global_max_daily_loss = models.DecimalField('全局最大日亏损(USD)', max_digits=14, decimal_places=2, default=500)
    global_stop_loss_pct = models.DecimalField('全局止损比例', max_digits=5, decimal_places=4, default=0.05)
    global_min_order_interval = models.DecimalField('全局最小下单间隔(秒)', max_digits=5, decimal_places=2, default=1.0)
    global_default_leverage = models.PositiveIntegerField('全局默认杠杆倍数', default=3)
    # 注册控制
    allow_registration = models.BooleanField('允许新用户注册', default=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'account_global_config'
        verbose_name = '全局配置'
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        self.id = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(id=1)
        return config
