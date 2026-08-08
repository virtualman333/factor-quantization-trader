import os
import sys
from django.core.wsgi import get_wsgi_application

# 强制 UTF-8，避免 Windows 下中文/时间乱码
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
