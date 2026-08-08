"""Redis 内存使用监控工具

提供 Redis INFO 的解析封装，供监控 API / Celery 任务使用。
注意：redis-py 4.x 的 info() 返回扁平 dict（不嵌套 section）。
"""
import logging

import redis as redis_lib

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_redis_connection():
    """从 Django CACHES 获取 Redis 连接"""
    location = settings.CACHES['default'].get('LOCATION', 'redis://localhost:6379/2')
    return redis_lib.from_url(location)


def _mb(val):
    """字节 -> 兆字节"""
    try:
        return round(int(val) / (1024 * 1024), 2)
    except (TypeError, ValueError):
        return None


def get_redis_memory_info() -> dict:
    """获取 Redis 内存使用信息（解析 INFO）"""
    conn = _get_redis_connection()
    info = conn.info()
    return {
        'server': {
            'redis_version': info.get('redis_version'),
            'uptime_seconds': info.get('uptime_in_seconds'),
            'connected_clients': info.get('connected_clients'),
        },
        'memory': {
            'used_memory': info.get('used_memory'),
            'used_memory_human': info.get('used_memory_human'),
            'used_memory_mb': _mb(info.get('used_memory')),
            'used_memory_peak': info.get('used_memory_peak'),
            'used_memory_peak_human': info.get('used_memory_peak_human'),
            'used_memory_peak_mb': _mb(info.get('used_memory_peak')),
            'maxmemory': info.get('maxmemory'),
            'maxmemory_human': info.get('maxmemory_human'),
            'maxmemory_policy': info.get('maxmemory_policy'),
            'mem_fragmentation_ratio': info.get('mem_fragmentation_ratio'),
        },
        'stats': {
            'total_connections_received': info.get('total_connections_received'),
            'total_commands_processed': info.get('total_commands_processed'),
            'expired_keys': info.get('expired_keys'),
            'evicted_keys': info.get('evicted_keys'),
        },
        'keyspace': {
            f'db{i}': {'keys': db.get('keys'), 'expires': db.get('expires')}
            for i, db in info.get('db', {}).items()
        },
    }


def redis_memory_summary() -> dict:
    """简短摘要（用于 Celery 定时任务记录日志）"""
    info = get_redis_memory_info()
    return {
        'version': info['server']['redis_version'],
        'used_mb': info['memory'].get('used_memory_mb'),
        'peak_mb': info['memory'].get('used_memory_peak_mb'),
        'clients': info['server']['connected_clients'],
        'frag_ratio': info['memory'].get('mem_fragmentation_ratio'),
        'dbs': info.get('keyspace', {}),
    }
