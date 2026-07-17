"""行情数据 Celery 定时任务"""
from celery import shared_task
from apps.market.services import MarketDataService


@shared_task
def sync_instruments_task():
    """定时同步交易品种"""
    for inst_type in ['SPOT', 'SWAP']:
        try:
            MarketDataService.sync_instruments(inst_type=inst_type)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Sync instruments {inst_type} failed: {e}')


@shared_task
def sync_tickers_task():
    """定时同步行情快照"""
    from apps.market.models import Instrument
    instruments = Instrument.objects.filter(is_active=True)[:50]  # 限制数量
    for inst in instruments:
        try:
            MarketDataService.sync_ticker(inst.inst_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Sync ticker {inst.inst_id} failed: {e}')


@shared_task
def sync_klines_task(inst_id: str, bar: str = '1H'):
    """定时同步K线"""
    try:
        MarketDataService.fetch_klines(inst_id=inst_id, bar=bar, limit=100)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Sync klines {inst_id} {bar} failed: {e}')
