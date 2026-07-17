"""订单 Celery 定时任务"""
from celery import shared_task
from apps.orders.services import OrderService


@shared_task
def sync_pending_orders_task():
    """定时同步待处理订单状态"""
    try:
        count = OrderService.sync_pending_orders()
        return {'synced': count}
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Sync orders failed: {e}')
        return {'error': str(e)}
