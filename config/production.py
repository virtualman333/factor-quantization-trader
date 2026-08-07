"""生产环境配置 —— 覆盖 settings.py 中的关键参数。

使用方式:
    DJANGO_SETTINGS_MODULE=config.production python manage.py runserver
    DJANGO_SETTINGS_MODULE=config.production celery -A config worker -l info
    DJANGO_SETTINGS_MODULE=config.production gunicorn config.wsgi
"""

from config.settings import *

# ── 安全 ─────────────────────────────────────────────────────────────────────
DEBUG = False
SECRET_KEY = env('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')

# ── HTTPS / HSTS ─────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# ── 数据库 (连接池) ──────────────────────────────────────────────────────────
DATABASES['default'].update({
    'CONN_MAX_AGE': 600,
    'CONN_HEALTH_CHECKS': True,
    'OPTIONS': {
        **DATABASES['default'].get('OPTIONS', {}),
        'init_command': (
            "SET sql_mode='STRICT_TRANS_TABLES'"
        ),
    },
})

# ── 缓存 ─────────────────────────────────────────────────────────────────────
CACHES['default']['OPTIONS'] = {
    'CLIENT_CLASS': 'django_redis.client.DefaultClient',
    'SOCKET_CONNECT_TIMEOUT': 5,
    'SOCKET_TIMEOUT': 5,
    'RETRY_ON_TIMEOUT': True,
    'MAX_CONNECTIONS': 50,
    'CONNECTION_POOL_KWARGS': {'max_connections': 50},
}

# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True

# ── DRF ──────────────────────────────────────────────────────────────────────
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
]
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].update({
    'anon': '10/minute',
    'user': '60/minute',
})

# ── Celery ───────────────────────────────────────────────────────────────────
CELERY_TASK_ALWAYS_EAGER = False
CELERY_WORKER_MAX_TASKS_PER_CHILD = 200
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200 MB
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# ── 日志 ─────────────────────────────────────────────────────────────────────
LOGGING['handlers']['console']['level'] = 'WARNING'
LOGGING['loggers']['django']['level'] = 'WARNING'
LOGGING['loggers']['django.server']['level'] = 'WARNING'
LOGGING['loggers']['django.db.backends']['level'] = 'ERROR'
LOGGING['root']['level'] = 'WARNING'

# ── 邮件 (错误通知) ──────────────────────────────────────────────────────────
ADMINS = [tuple(item.split(':')) for item in env.list('DJANGO_ADMINS', default=[])]
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
SERVER_EMAIL = env('SERVER_EMAIL', default='noreply@factor-quantization-trader.com')

# ── OKX ──────────────────────────────────────────────────────────────────────
OKX_CONFIG['DEBUG'] = False
