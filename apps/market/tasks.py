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
    instruments = Instrument.objects.filter(is_active=True)[:50]
    for inst in instruments:
        try:
            MarketDataService.sync_ticker(inst.inst_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'Sync ticker {inst.inst_id} failed: {e}')


@shared_task
def sync_klines_task(inst_id: str, bar: str = '1H'):
    """定时同步最新K线"""
    try:
        MarketDataService.fetch_klines(inst_id=inst_id, bar=bar, limit=100)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Sync klines {inst_id} {bar} failed: {e}')


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def async_fetch_klines_task(self, inst_id: str, bar: str, total: int = 500, before: str = ''):
    """异步从 OKX 拉取历史 K 线并存入数据库（后台执行，不阻塞前端请求）。
    用于 scroll 接口发现数据库无数据时触发后台补齐。
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        count = MarketDataService.fetch_klines_history(
            inst_id=inst_id, bar=bar, total=total, before=before
        )
        logger.info(f'[async_fetch] {inst_id} {bar}: 后台拉取完成，共 {count} 条')
        return count
    except Exception as e:
        logger.error(f'[async_fetch] {inst_id} {bar} failed: {e}')
        try:
            self.retry(exc=e)
        except Exception:
            pass
        return 0
