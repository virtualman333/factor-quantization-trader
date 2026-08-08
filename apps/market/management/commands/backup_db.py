"""数据库备份命令（dumpdata + 可选 mysqldump）

用法:
  python manage.py backup_db                                # 备份到 backups/ 目录
  python manage.py backup_db --format sql                   # 用 mysqldump 备份
  python manage.py backup_db --keep 10                      # 仅保留最近10份
"""
import datetime
import os
import subprocess

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '数据库备份'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=['json', 'sql'], default='json',
                            help='备份格式: json(dumpdata) / sql(mysqldump)')
        parser.add_argument('--keep', type=int, default=10, help='保留最近N份备份')
        parser.add_argument('--out', default='', help='备份目录，默认 backups/')

    def handle(self, *args, **options):
        fmt = options['format']
        keep = options['keep']
        out_dir = options['out'] or os.path.join(str(settings.BASE_DIR), 'backups')
        os.makedirs(out_dir, exist_ok=True)

        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = f'backup_{stamp}'

        if fmt == 'json':
            filename = f'{prefix}.json'
            filepath = os.path.join(out_dir, filename)
            self.stdout.write(f'正在导出 JSON 备份...')
            with open(filepath, 'w', encoding='utf-8') as f:
                call_command('dumpdata', '--exclude', 'sessions', '--exclude', 'contenttypes',
                             stdout=f)
            self.stdout.write(self.style.SUCCESS(f'JSON 备份完成: {filepath}'))
        else:
            # mysqldump 备份
            db = settings.DATABASES['default']
            if db['ENGINE'].endswith('mysql'):
                filename = f'{prefix}.sql'
                filepath = os.path.join(out_dir, filename)
                cmd = [
                    'mysqldump', f'-u{db["USER"]}',
                    f'-p{db.get("PASSWORD", "")}', '-h', db.get('HOST', '127.0.0.1'),
                    db['NAME'],
                ]
                self.stdout.write(f'正在执行 mysqldump...')
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        subprocess.run(cmd, stdout=f, check=True)
                    self.stdout.write(self.style.SUCCESS(f'SQL 备份完成: {filepath}'))
                except FileNotFoundError:
                    self.stderr.write('未找到 mysqldump，请确保 MySQL 客户端已安装')
                    return
            else:
                self.stderr.write('非 MySQL 数据库，回退为 JSON 备份')
                return

        # 清理旧备份
        backups = sorted([
            os.path.join(out_dir, f) for f in os.listdir(out_dir)
            if f.startswith('backup_')
        ])
        if len(backups) > keep:
            for old in backups[:-keep]:
                os.remove(old)
                self.stdout.write(f'清理旧备份: {os.path.basename(old)}')

        self.stdout.write(self.style.SUCCESS(f'备份完成，保留 {min(len(backups), keep)} 份'))
