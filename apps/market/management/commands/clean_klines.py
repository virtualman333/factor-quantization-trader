"""K 线数据自动清理命令

清理过期的 K 线数据（按品种保留最新 N 条 / 按天数保留）。

用法:
  python manage.py clean_klines --inst BTC-USDT --bar 1H --keep 5000
  python manage.py clean_klines --all-bars --days 90          # 删除90天前的全部K线
  python manage.py clean_klines --dry-run                      # 只统计不删除
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.market.models import KLine


class Command(BaseCommand):
    help = 'K线数据清理：按条数保留或按时间删除过期数据'

    def add_arguments(self, parser):
        parser.add_argument('--inst', default='', help='品种ID，留空则所有品种')
        parser.add_argument('--bar', default='', help='周期，如 1H/1D，留空则所有周期')
        parser.add_argument('--keep', type=int, default=0, help='每个(品种,周期)保留最新N条，0=不按条数清理')
        parser.add_argument('--days', type=int, default=0, help='删除N天前的数据，0=不按时间清理')
        parser.add_argument('--dry-run', action='store_true', help='仅统计，不实际删除')

    def handle(self, *args, **options):
        inst = options['inst']
        bar = options['bar']
        keep = options['keep']
        days = options['days']
        dry_run = options['dry_run']

        if not keep and not days:
            self.stderr.write('请至少指定 --keep 或 --days 之一')
            return

        qs = KLine.objects.select_related('instrument').all()
        if inst:
            qs = qs.filter(instrument__inst_id=inst)
        if bar:
            qs = qs.filter(bar=bar)

        total = qs.count()
        self.stdout.write(f'总记录: {total}')

        deleted_total = 0

        # 按时间删除
        if days:
            cutoff = timezone.now() - timedelta(days=days)
            old_qs = qs.filter(timestamp__lt=cutoff)
            old_count = old_qs.count()
            self.stdout.write(f'按时间删除 ({days}天前): {old_count} 条')
            if old_count and not dry_run:
                deleted_total += old_qs.delete()[0]

        # 按条数保留
        if keep:
            # 对每个 (品种, 周期) 分组，删除超出 keep 的旧数据
            keys = (qs.order_by('instrument_id', 'bar')
                    .values_list('instrument_id', 'bar').distinct())
            for inst_id, bar_val in keys:
                group = qs.filter(instrument_id=inst_id, bar=bar_val).order_by('-timestamp')
                count = group.count()
                if count <= keep:
                    continue
                keep_ids = list(group.values_list('id', flat=True)[:keep])
                excess = group.exclude(id__in=keep_ids)
                excess_count = excess.count()
                self.stdout.write(f'{inst_id}/{bar_val}: 共{count}, 清理{excess_count}')
                if excess_count and not dry_run:
                    deleted_total += excess.delete()[0]

        if dry_run:
            self.stdout.write(self.style.WARNING('dry-run 模式，未实际删除'))
        else:
            self.stdout.write(self.style.SUCCESS(f'清理完成，共删除 {deleted_total} 条'))
