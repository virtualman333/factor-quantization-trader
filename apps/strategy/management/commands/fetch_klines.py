"""Django管理命令: 拉取K线数据"""
from django.core.management.base import BaseCommand
from apps.market.services import MarketDataService


class Command(BaseCommand):
    help = '从 OKX 拉取K线数据并存储到本地'

    def add_arguments(self, parser):
        parser.add_argument('--inst_id', '-i', type=str, required=True, help='产品ID, 如 BTC-USDT')
        parser.add_argument('--bar', '-b', type=str, default='1H', help='K线周期 (默认: 1H)')
        parser.add_argument('--limit', '-l', type=int, default=200, help='拉取数量 (默认: 200)')
        parser.add_argument('--history', action='store_true', default=True,
                            help='使用历史K线接口 (默认: True)')

    def handle(self, *args, **options):
        inst_id = options['inst_id']
        bar = options['bar']
        limit = options['limit']
        is_history = options['history']

        self.stdout.write(f'正在拉取 {inst_id} {bar} K线 (x{limit})...')
        klines = MarketDataService.fetch_klines(
            inst_id=inst_id, bar=bar, limit=limit, is_history=is_history
        )
        if klines:
            self.stdout.write(self.style.SUCCESS(
                f'拉取完成: {len(klines)} 条 K线 '
                f'[{klines[0].timestamp.strftime("%Y-%m-%d %H:%M")} ~ '
                f'{klines[-1].timestamp.strftime("%Y-%m-%d %H:%M")}]'
            ))
        else:
            self.stdout.write(self.style.WARNING('无数据返回'))
