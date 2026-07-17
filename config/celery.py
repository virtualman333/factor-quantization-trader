import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('factor_quantization_trader')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
