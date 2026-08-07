"""K 线数据导出命令（CSV）

用法:
  python manage.py export_klines --inst BTC-USDT --bar 1H --out klines.csv
  python manage.py export_klines --inst BTC-USDT --days 30 --format csv
"""
import csv
import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.market.models import KLine


class Command(BaseCommand):
    help = '导出K线数据为CSV'

    def add_arguments(self, parser):
        parser.add_argument('--inst', required=True, help='品种ID')
        parser.add_argument('--bar', default='1H', help='周期')
        parser.add_argument('--days', type=int, default=0, help='导出最近N天，0=全部')
        parser.add_argument('--env', default='demo', help='环境: demo/live')
        parser.add_argument('--out', default='', help='输出文件路径，默认 klines_{inst}_{bar}.csv')

    def handle(self, *args, **options):
        inst = options['inst']
        bar = options['bar']
        days = options['days']
        env = options['env']
        out = options['out'] or f'klines_{inst}_{bar}.csv'

        qs = KLine.objects.filter(
            instrument__inst_id=inst, bar=bar, environment=env
        ).order_by('timestamp')
        if days:
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(timestamp__gte=cutoff)

        rows = list(qs)
        if not rows:
            self.stderr.write('无数据可导出')
            return

        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'open', 'high', 'low', 'close', 'vol', 'vol_ccy', 'confirm'])
            for r in rows:
                writer.writerow([
                    r.timestamp.isoformat(),
                    r.open, r.high, r.low, r.close,
                    r.vol, r.vol_ccy or '', r.confirm,
                ])

        self.stdout.write(self.style.SUCCESS(f'已导出 {len(rows)} 条到 {out}'))
