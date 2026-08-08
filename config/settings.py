import os
from datetime import timedelta

import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
env_file = os.environ.get('ENV_FILE', os.path.join(BASE_DIR, '.env'))
if os.path.exists(env_file):
    environ.Env.read_env(env_file)

ENVIRONMENT = env('DJANGO_ENVIRONMENT', default='development')

SECRET_KEY = env('DJANGO_SECRET_KEY', default='dev-secret-key-change-in-production')
DEBUG = env.bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['*'])

INSTALLED_APPS = [
    # 注: 不使用 Django 自带 /admin/，管理端由前端 Vue 实现 (apps/account/admin_views.py)
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    # Local apps
    'apps.market.MarketConfig',
    'apps.account.AccountConfig',
    'apps.strategy.StrategyConfig',
    'apps.orders.OrdersConfig',
    'apps.notifications.NotificationsConfig',
]

# ---- 可选：drf-spectacular (OpenAPI 3.0 + Swagger UI) ----
# pip install drf-spectacular 后自动启用。未安装时保持兼容。
try:
    import drf_spectacular  # noqa: F401
    INSTALLED_APPS += ['drf_spectacular']
except ImportError:
    drf_spectacular = None

if drf_spectacular is not None:
    SPECTACULAR_SETTINGS = {
        'TITLE': 'Factor Quant Trader API',
        'DESCRIPTION': '因子量化交易系统 — 后端 API 文档与在线调试界面。\n'
                       '默认需要登录（JWT Bearer Token 或 Session）。'
                       '在生产环境（DEBUG=False）下请关闭 AllowAny。',
        'VERSION': '1.0.0',
        'SERVE_INCLUDE_SCHEMA': True,
        'SCHEMA_PATH_PREFIX': '/api/',
        'COMPONENT_SPLIT_REQUEST': True,
        'ENUM_NAME_OVERRIDES': {
            'StrategyTypeEnum': 'apps.strategy.models.StrategyConfig.STRATEGY_TYPE_CHOICES',
            'OrderStateEnum': 'apps.orders.models.TradeOrder.STATE_CHOICES',
        },
    }

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'core.middleware.RequestLogMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ApiErrorMiddleware',
    'core.quota_middleware.UserQuotaMiddleware',
]

# ---- 性能监控（仅开发环境启用，生产环境由 DJANGO_DEBUG=False 关闭） ----
if DEBUG:
    INSTALLED_APPS += ['silk', 'debug_toolbar']
    MIDDLEWARE = MIDDLEWARE + [
        'silk.middleware.SilkyMiddleware',
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]
    # Debug Toolbar：仅本地回环 IP 显示（避免 API JSON 响应被注入）
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG and request.META.get('REMOTE_ADDR') in (
            '127.0.0.1', 'localhost',
        ),
        'SHOW_COLLAPSED': True,
    }
    # Silk：请求性能分析（数据保存在 DB，访问 /silk/）
    SILKY_PYTHON_PROFILER = False
    SILKY_AUTHENTICATION = False
    SILKY_META = True
    SILKY_MAX_RECORDED_REQUESTS = 2000

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('MYSQL_DATABASE', default='factor'),
        'USER': env('MYSQL_USER', default='factor'),
        'PASSWORD': env('MYSQL_PASSWORD', default='factor'),
        'HOST': env('MYSQL_HOST', default='127.0.0.1'),
        'PORT': env('MYSQL_PORT', default='3306'),
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            # 长耗时操作（回测/优化）时保持连接活跃
            'connect_timeout': 10,
            'read_timeout': 300,
            'write_timeout': 300,
        },
    }
}

# Cache
# NOTE: redis-py 已锁定 <5.0（兼容旧版 Redis 3.x，不发送 HELLO/RESP3 命令）
_redis_password = env('REDIS_PASSWORD', default='')
_redis_auth = f':{_redis_password}@' if _redis_password else ''
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': f'redis://{_redis_auth}127.0.0.1:6379/2',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
        'login': '5/minute',
    },
    'EXCEPTION_HANDLER': 'core.exception_handler.custom_exception_handler',
}

if drf_spectacular is not None:
    REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'

# CORS
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True
if not DEBUG:
    CORS_ALLOWED_ORIGINS = env.list(
        'CORS_ALLOWED_ORIGINS',
        default=[
            'http://localhost:5173',
            'http://127.0.0.1:5173',
        ],
    )
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
# 记录任务参数（用于前端展示进行中的回测任务）
CELERY_RESULT_EXTENDED = True
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# 默认定时任务（可通过 django-celery-beat 管理界面调整）
CELERY_BEAT_SCHEDULE = {
    'run-active-strategies-every-minute': {
        'task': 'apps.strategy.tasks.run_active_strategies',
        'schedule': 60.0,  # 每分钟
    },
    'execute-pending-signals-every-minute': {
        'task': 'apps.strategy.tasks.execute_pending_signals',
        'schedule': 60.0,
    },
    # Redis 内存监控（每 10 分钟）
    'redis-memory-monitor-every-10min': {
        'task': 'apps.account.tasks.redis_memory_monitor_task',
        'schedule': 600.0,
    },
    # K 线数据清理（每天凌晨 3 点）
    'clean-klines-every-day': {
        'task': 'apps.market.tasks.clean_klines_task',
        'schedule': 3 * 60 * 60,
    },
    # 交易品种定时同步（每天 4 点，SPOT + SWAP）
    'sync-instruments-every-day': {
        'task': 'apps.market.tasks.sync_instruments_task',
        'schedule': 4 * 60 * 60,
        'args': ['ALL'],
    },
}


# OKX Configuration
OKX_CONFIG = {
    'API_KEY': env('OKX_API_KEY', default=''),
    'API_SECRET': env('OKX_API_SECRET', default=''),
    'PASSPHRASE': env('OKX_PASSPHRASE', default=''),
    'FLAG': env('OKX_FLAG', default='1'),  # 0=live, 1=demo
    'DEBUG': DEBUG,
}

# Risk Management
RISK_CONFIG = {
    'MAX_POSITION_PCT': env.float('MAX_POSITION_PCT', default=0.2),
    'MAX_ORDER_VALUE': env.float('MAX_ORDER_VALUE', default=10000),
    'MAX_DAILY_LOSS': env.float('MAX_DAILY_LOSS', default=500),
    'STOP_LOSS_PCT': env.float('STOP_LOSS_PCT', default=0.05),
    'DEFAULT_LEVERAGE': 3,
    'MIN_ORDER_INTERVAL': 1.0,  # seconds
}

# ── Logging ──────────────────────────────────────────────────────────────────
from config.logging_config import LOGGING  # noqa: E402

# ── Sentry (optional) ────────────────────────────────────────────────────────
SENTRY_DSN = env('SENTRY_DSN', default='')
if SENTRY_DSN and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    import logging as sentry_logging
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(
                level=sentry_logging.INFO,
                event_level=sentry_logging.ERROR,
            ),
        ],
        environment=ENVIRONMENT,
        traces_sample_rate=0.1 if ENVIRONMENT == 'production' else 1.0,
        send_default_pii=False,
    )
