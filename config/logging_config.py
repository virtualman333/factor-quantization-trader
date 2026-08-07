import os
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = os.environ.get('LOG_DIR', str(BASE_DIR / 'logs'))

os.makedirs(LOG_DIR, exist_ok=True)


class SlowQueryFilter(logging.Filter):
    """慢查询过滤器：仅记录耗时 >= 1s 的 SQL"""

    def filter(self, record):
        return getattr(record, 'duration', 0) >= 1.0

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {process:d} {thread:d} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{asctime}] {levelname} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'request': {
            'format': '[{asctime}] {levelname} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'celery': {
            'format': '[{asctime}] {levelname} [{name}] task={celery_task_name} id={celery_task_id} | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'json': {
            'format': '{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", '
                      '"lineno": %(lineno)d, "process": %(process)d, "thread": %(thread)d, '
                      '"message": "%(message)s"}',
            'style': '%',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
        'slow_query': {
            'format': '[{asctime}] {levelname} {duration:.3f}s | {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'skip_static_requests': {
            '()': 'core.log_filters.SkipStaticRequestsFilter',
        },
        'slow_query': {
            '()': 'config.logging_config.SlowQueryFilter',
        },
    },
    'handlers': {
        'file_slow_query': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'slow_queries.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'slow_query',
            'filters': ['slow_query'],
            'encoding': 'utf-8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['skip_static_requests'],
        },
        'console_debug': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['require_debug_true', 'skip_static_requests'],
        },
        'file_app': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 30,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'error.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 90,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_warning': {
            'level': 'WARNING',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'warning.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 60,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'file_request': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'request.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 30,
            'formatter': 'request',
            'encoding': 'utf-8',
        },
        'file_celery': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'celery.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 30,
            'formatter': 'celery',
            'encoding': 'utf-8',
        },
        'file_celery_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'celery_error.log'),
            'when': 'midnight',
            'interval': 1,
            'backupCount': 90,
            'formatter': 'celery',
            'encoding': 'utf-8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_app', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console', 'file_app'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file_error', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file_slow_query'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'api.request': {
            'handlers': ['console', 'file_request'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file_celery', 'file_celery_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.task': {
            'handlers': ['console', 'file_celery', 'file_celery_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.beat': {
            'handlers': ['console', 'file_celery'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file_app', 'file_error', 'file_warning'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file_app', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'okx': {
            'handlers': ['console', 'file_app', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
        'config': {
            'handlers': ['console', 'file_app', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file_error'],
        'level': 'WARNING',
    },
}
