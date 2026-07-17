"""
策略模型：策略配置、因子定义、信号记录、回测结果
"""

from django.db import models



class StrategyConfig(models.Model):
    """策略配置"""

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '运行中'),
        ('paused', '已暂停'),
        ('stopped', '已停止'),
    ]

    DIRECTION_CHOICES = [
        ('long', '只做多'),
        ('short', '只做空'),
        ('both', '多空双向'),
    ]

    TD_MODE_CHOICES = [
        ('cash', '现金/现货'),
        ('cross', '全仓合约'),
        ('isolated', '逐仓合约'),
    ]

    STRATEGY_TYPE_CHOICES = [
        ('factor_composite', '因子综合评分'),
        ('trend_follow', '趋势跟踪'),
    ]

    name = models.CharField('策略名称', max_length=100, unique=True)
    description = models.TextField('策略描述', blank=True)
    strategy_type = models.CharField('策略类型', max_length=30, choices=STRATEGY_TYPE_CHOICES, default='factor_composite')
    inst_type = models.CharField('产品类型', max_length=20, default='SWAP')
    symbols = models.JSONField('交易标的列表', default=list,
                                help_text='例如: ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]')
    bar = models.CharField('K线周期', max_length=10, default='1H')
    direction = models.CharField('交易方向', max_length=10, choices=DIRECTION_CHOICES, default='long')
    status = models.CharField('策略状态', max_length=10, choices=STATUS_CHOICES, default='draft')

    # 合约参数
    td_mode = models.CharField('保证金模式', max_length=10, choices=TD_MODE_CHOICES, default='cross',
                                help_text='合约交易使用 cross 全仓或 isolated 逐仓')
    leverage = models.DecimalField('杠杆倍数', max_digits=6, decimal_places=2, default=3,
                                    help_text='例如 3 = 3x 杠杆')

    # 资金与风控参数
    initial_capital = models.DecimalField('初始资金(USD)', max_digits=20, decimal_places=4, default=0)
    order_size_pct = models.DecimalField('每次下单比例', max_digits=6, decimal_places=4, default=0.1,
                                          help_text='0.1 = 每次使用保证金的10%')
    max_positions = models.IntegerField('最大持仓数', default=5)
    stop_loss_pct = models.DecimalField('止损比例', max_digits=6, decimal_places=4, default=0.05)
    take_profit_pct = models.DecimalField('止盈比例', max_digits=6, decimal_places=4, default=0.10)

    # 因子配置
    factors = models.JSONField('使用因子列表', default=list,
                                help_text='例如: ["momentum", "volatility", "rsi", "macd"]')

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'strategy_config'
        verbose_name = '策略配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'



class FactorDefinition(models.Model):
    """因子定义"""

    FACTOR_TYPE_CHOICES = [
        ('trend', '趋势类'),
        ('momentum', '动量类'),
        ('volatility', '波动类'),
        ('volume', '成交量类'),
        ('composite', '复合类'),
    ]

    name = models.CharField('因子名称', max_length=50, unique=True)
    display_name = models.CharField('显示名称', max_length=100)
    factor_type = models.CharField('因子类型', max_length=20, choices=FACTOR_TYPE_CHOICES)
    description = models.TextField('因子描述', blank=True)
    params = models.JSONField('因子参数', default=dict, help_text='JSON格式的参数配置')
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'strategy_factor_definition'
        verbose_name = '因子定义'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.display_name} ({self.get_factor_type_display()})'


class SignalRecord(models.Model):
    """交易信号记录"""

    SIGNAL_CHOICES = [
        ('buy', '买入/开多'),
        ('sell', '卖出/开空'),
        ('close_long', '平多'),
        ('close_short', '平空'),
        ('hold', '持有'),
    ]

    POS_SIDE_CHOICES = [
        ('long', '多头'),
        ('short', '空头'),
        ('net', '净仓'),
    ]

    strategy = models.ForeignKey(StrategyConfig, on_delete=models.CASCADE,
                                  related_name='signals', verbose_name='所属策略')
    inst_id = models.CharField('交易标的', max_length=50)
    signal = models.CharField('信号类型', max_length=20, choices=SIGNAL_CHOICES)
    pos_side = models.CharField('持仓方向', max_length=10, choices=POS_SIDE_CHOICES, blank=True)
    td_mode = models.CharField('保证金模式', max_length=10, blank=True)
    leverage = models.DecimalField('杠杆倍数', max_digits=6, decimal_places=2, default=1)
    score = models.DecimalField('信号评分', max_digits=8, decimal_places=4, default=0,
                                 help_text='综合因子量化评分, 0~1')
    factors_detail = models.JSONField('各因子详情', default=dict,
                                       help_text='{"momentum": 0.8, "rsi": 0.3}')
    price = models.DecimalField('当前价格', max_digits=24, decimal_places=8, null=True)
    reason = models.TextField('信号原因', blank=True)
    is_executed = models.BooleanField('是否已执行', default=False)
    created_at = models.DateTimeField('信号时间', auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'strategy_signal'
        verbose_name = '交易信号'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.strategy.name} - {self.inst_id} {self.get_signal_display()} ({self.score:.2f})'



class BacktestResult(models.Model):
    """回测结果"""

    strategy = models.ForeignKey(StrategyConfig, on_delete=models.CASCADE,
                                  related_name='backtests', verbose_name='所属策略')
    start_date = models.DateTimeField('回测开始')
    end_date = models.DateTimeField('回测结束')
    initial_capital = models.DecimalField('初始资金', max_digits=20, decimal_places=4)
    final_capital = models.DecimalField('最终资金', max_digits=20, decimal_places=4)
    total_return = models.DecimalField('总收益率', max_digits=8, decimal_places=6)
    annual_return = models.DecimalField('年化收益率', max_digits=8, decimal_places=6, null=True)
    sharpe_ratio = models.DecimalField('夏普比率', max_digits=8, decimal_places=4, null=True)
    max_drawdown = models.DecimalField('最大回撤率', max_digits=8, decimal_places=6)
    win_rate = models.DecimalField('胜率', max_digits=6, decimal_places=4)
    total_trades = models.IntegerField('总交易次数')
    profit_trades = models.IntegerField('盈利交易')
    loss_trades = models.IntegerField('亏损交易')
    avg_profit = models.DecimalField('平均盈利', max_digits=20, decimal_places=4, null=True)
    avg_loss = models.DecimalField('平均亏损', max_digits=20, decimal_places=4, null=True)
    profit_factor = models.DecimalField('盈亏比', max_digits=8, decimal_places=4, null=True)
    equity_curve = models.JSONField('权益曲线', default=list)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'strategy_backtest'
        verbose_name = '回测结果'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.strategy.name} 回测 [{self.start_date.date()}~{self.end_date.date()}] 收益: {self.total_return:.2%}'
