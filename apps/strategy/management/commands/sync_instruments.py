"""Django管理命令: 同步交易品种"""
from django.core.management.base import BaseCommand
from apps.market.services import MarketDataService


class Command(BaseCommand):
    help = '从 OKX 同步交易品种信息到本地数据库'

    def add_arguments(self, parser):
        parser.add_argument('--type', '-t', type=str, default='SPOT',
                            choices=['SPOT', 'MARGIN', 'SWAP', 'FUTURES', 'OPTION'],
                            help='产品类型 (默认: SPOT)')

    def handle(self, *args, **options):
        inst_type = options['type']
        self.stdout.write(f'正在同步 {inst_type} 品种...')
        count = MarketDataService.sync_instruments(inst_type=inst_type)
        self.stdout.write(self.style.SUCCESS(f'同步完成，共 {count} 个品种'))
