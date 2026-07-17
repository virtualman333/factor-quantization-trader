"""
行情数据模型
存储交易品种基础信息、K线数据、行情快照
"""

from django.db import models


class Instrument(models.Model):
    """交易品种信息"""

    INST_TYPE_CHOICES = [
        ('SPOT', '现货'),
        ('MARGIN', '杠杆'),
        ('SWAP', '永续合约'),
        ('FUTURES', '交割合约'),
        ('OPTION', '期权'),
    ]

    inst_id = models.CharField('交易品种ID', max_length=50, unique=True, db_index=True)
    inst_type = models.CharField('产品类型', max_length=20, choices=INST_TYPE_CHOICES)
    uly = models.CharField('标的指数', max_length=50, default='')
    base_ccy = models.CharField('基础币种', max_length=20, default='')
    quote_ccy = models.CharField('计价币种', max_length=20, default='')
    ct_val = models.CharField('合约面值', max_length=50, default='')
    ct_mult = models.CharField('合约乘数', max_length=50, default='')
    lot_sz = models.CharField('最小下单数量', max_length=50, default='')
    min_sz = models.CharField('最小下单数量', max_length=50, default='')
    tick_sz = models.CharField('价格精度', max_length=50, default='')
    state = models.CharField('产品状态', max_length=20, default='live')  # live / suspend
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'market_instrument'
        verbose_name = '交易品种'
        verbose_name_plural = verbose_name
        ordering = ['inst_id']

    def __str__(self):
        return f'{self.inst_id} ({self.get_inst_type_display()})'


class KLine(models.Model):
    """K线数据"""

    BAR_CHOICES = [
        ('1m', '1分钟'),
        ('3m', '3分钟'),
        ('5m', '5分钟'),
        ('15m', '15分钟'),
        ('30m', '30分钟'),
        ('1H', '1小时'),
        ('2H', '2小时'),
        ('4H', '4小时'),
        ('6H', '6小时'),
        ('12H', '12小时'),
        ('1D', '1天'),
        ('1W', '1周'),
        ('1M', '1月'),
    ]

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE,
                                    related_name='klines', verbose_name='交易品种')
    bar = models.CharField('K线周期', max_length=10, choices=BAR_CHOICES)
    timestamp = models.DateTimeField('K线时间', db_index=True)
    open = models.DecimalField('开盘价', max_digits=24, decimal_places=8)
    high = models.DecimalField('最高价', max_digits=24, decimal_places=8)
    low = models.DecimalField('最低价', max_digits=24, decimal_places=8)
    close = models.DecimalField('收盘价', max_digits=24, decimal_places=8)
    vol = models.DecimalField('成交量', max_digits=24, decimal_places=8, default=0)
    vol_ccy = models.DecimalField('成交额(计价币)', max_digits=24, decimal_places=8, default=0)
    vol_ccy_quote = models.DecimalField('成交额(USD)', max_digits=24, decimal_places=8, default=0)
    confirm = models.IntegerField('K线状态', default=0)  # 0=未完成, 1=已完成
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'market_kline'
        verbose_name = 'K线数据'
        verbose_name_plural = verbose_name
        unique_together = [('instrument', 'bar', 'timestamp')]
        indexes = [
            models.Index(fields=['instrument', 'bar', 'timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.instrument.inst_id} {self.get_bar_display()} @ {self.timestamp}'


class Ticker(models.Model):
    """行情快照"""

    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE,
                                    related_name='tickers', verbose_name='交易品种')
    last = models.DecimalField('最新价', max_digits=24, decimal_places=8, null=True)
    open_24h = models.DecimalField('24h开盘价', max_digits=24, decimal_places=8, null=True)
    high_24h = models.DecimalField('24h最高价', max_digits=24, decimal_places=8, null=True)
    low_24h = models.DecimalField('24h最低价', max_digits=24, decimal_places=8, null=True)
    vol_24h = models.DecimalField('24h成交量', max_digits=24, decimal_places=8, null=True)
    vol_ccy_24h = models.DecimalField('24h成交额', max_digits=24, decimal_places=8, null=True)
    bid_px = models.DecimalField('买一价', max_digits=24, decimal_places=8, null=True)
    bid_sz = models.DecimalField('买一量', max_digits=24, decimal_places=8, null=True)
    ask_px = models.DecimalField('卖一价', max_digits=24, decimal_places=8, null=True)
    ask_sz = models.DecimalField('卖一量', max_digits=24, decimal_places=8, null=True)
    timestamp = models.DateTimeField('行情时间', auto_now=True)

    class Meta:
        db_table = 'market_ticker'
        verbose_name = '行情快照'
        verbose_name_plural = verbose_name
        ordering = ['instrument__inst_id']

    def __str__(self):
        return f'{self.instrument.inst_id} @ {self.last}'


class FundingRate(models.Model):
    """资金费率"""
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE,
                                    related_name='funding_rates', verbose_name='交易品种')
    funding_rate = models.DecimalField('资金费率', max_digits=12, decimal_places=8)
    funding_time = models.DateTimeField('结算时间', db_index=True)
    realized_rate = models.DecimalField('实际费率', max_digits=12, decimal_places=8, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'market_funding_rate'
        verbose_name = '资金费率'
        verbose_name_plural = verbose_name
        unique_together = [('instrument', 'funding_time')]

    def __str__(self):
        return f'{self.instrument.inst_id} rate={self.funding_rate} @ {self.funding_time}'
