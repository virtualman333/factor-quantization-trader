"""账户 Celery 定时任务"""
from celery import shared_task
from apps.account.services import AccountService


@shared_task
def snapshot_account_task():
    """定时保存账户快照"""
    try:
        AccountService.snapshot_balance()
        AccountService.snapshot_positions()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Account snapshot failed: {e}')


@shared_task
def record_net_value_task():
    """定时记录净值"""
    try:
        AccountService.record_net_value()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Net value record failed: {e}')


@shared_task
def redis_memory_monitor_task():
    """定时监控 Redis 内存使用，写入日志（slow_queries 同目录 app.log）"""
    import logging
    logger = logging.getLogger('redis.monitor')
    try:
        from core.redis_monitor import redis_memory_summary
        summary = redis_memory_summary()
        logger.info(
            '[Redis监控] version=%s used=%sMB peak=%sMB clients=%s frag=%s dbs=%s',
            summary.get('version'), summary.get('used_mb'),
            summary.get('peak_mb'), summary.get('clients'),
            summary.get('frag_ratio'), summary.get('dbs'),
        )
    except Exception as e:
        logger.error(f'Redis memory monitor failed: {e}')
