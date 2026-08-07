import os
import sys
from celery import Celery

# 强制 UTF-8，避免 Windows 下中文/时间乱码
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('factor_quantization_trader')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
