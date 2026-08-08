"""K 线数据导入命令（CSV）

CSV 格式: timestamp,open,high,low,close,vol,vol_ccy,confirm
timestamp 支持 ISO 格式 (2026-08-07T00:00:00+08:00) 或毫秒时间戳

用法:
  python manage.py import_klines --inst BTC-USDT --bar 1H --file klines.csv
"""
import csv
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from apps.market.models import Instrument, KLine
from apps.market.services import MarketDataService


class Command(BaseCommand):
    help = '从CSV导入K线数据'

    def add_arguments(self, parser):
        parser.add_argument('--inst', required=True, help='品种ID')
        parser.add_argument('--bar', default='1H', help='周期')
        parser.add_argument('--file', required=True, help='CSV文件路径')
        parser.add_argument('--env', default='demo', help='环境: demo/live')
        parser.add_argument('--update', action='store_true', help='已存在时更新')

    def handle(self, *args, **options):
        inst_id = options['inst']
        bar = options['bar']
        filepath = options['file']
        env = options['env']
        update = options['update']

        instrument = Instrument.objects.filter(inst_id=inst_id).first()
        if not instrument:
            instrument = Instrument.objects.create(
                inst_id=inst_id, inst_type='SPOT',
                base_ccy=inst_id.split('-')[0],
                quote_ccy=inst_id.split('-')[1] if '-' in inst_id else 'USDT',
            )
            self.stdout.write(f'创建品种: {inst_id}')

        def _parse_ts(value):
            value = value.strip()
            try:
                # ISO 格式
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                try:
                    # 毫秒时间戳
                    return datetime.fromtimestamp(int(value) / 1000)
                except ValueError:
                    raise ValueError(f'无法解析时间: {value}')

        inserted = 0
        updated = 0
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header and header[0].lower() in ('timestamp', 'time'):
                pass  # 跳过表头
            else:
                # 无表头，将第一行作为数据
                if header:
                    import itertools
                    reader = itertools.chain([header], reader)

            batch = []
            for row in reader:
                if len(row) < 6:
                    continue
                ts = _parse_ts(row[0])
                if timezone.is_naive(ts):
                    ts = timezone.make_aware(ts)
                batch.append(KLine(
                    instrument=instrument,
                    environment=env,
                    bar=bar,
                    timestamp=ts,
                    open=Decimal(str(row[1])),
                    high=Decimal(str(row[2])),
                    low=Decimal(str(row[3])),
                    close=Decimal(str(row[4])),
                    vol=Decimal(str(row[5])),
                    vol_ccy=Decimal(str(row[6])) if len(row) > 6 and row[6] else None,
                    confirm=int(row[7]) if len(row) > 7 and row[7] else 1,
                ))

        # 去重：已存在时间戳
        existing = set(
            KLine.objects.filter(
                instrument=instrument, environment=env, bar=bar,
                timestamp__in=[b.timestamp for b in batch],
            ).values_list('timestamp', flat=True)
        )
        if update:
            updated = len(existing)
            KLine.objects.filter(
                instrument=instrument, environment=env, bar=bar,
                timestamp__in=existing,
            ).delete()
        to_insert = [b for b in batch if b.timestamp not in existing]
        if to_insert:
            KLine.objects.bulk_create(to_insert, batch_size=500)
            inserted = len(to_insert)

        self.stdout.write(self.style.SUCCESS(
            f'导入完成: 新增 {inserted} 条, 更新 {updated} 条, 跳过 {len(batch) - inserted - updated} 条'
        ))
