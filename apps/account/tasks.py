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
