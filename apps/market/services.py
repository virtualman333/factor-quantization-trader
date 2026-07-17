"""
行情数据服务层
负责从 OKX 获取行情并存储到本地数据库
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict

from django.db import transaction
from django.utils import timezone

from core.okx_client import get_okx_client
from core.exceptions import MarketDataUnavailable
from apps.market.models import Instrument, KLine, Ticker, FundingRate

logger = logging.getLogger(__name__)


class MarketDataService:
    """行情数据服务"""

    # ========== 交易品种 ==========
    @staticmethod
    def sync_instruments(inst_type: str = 'SPOT') -> int:
        """同步交易品种信息到本地数据库"""
        client = get_okx_client()
        result = client.get_instruments(inst_type=inst_type)
        if result['code'] != '0':
            raise MarketDataUnavailable(f'获取品种信息失败: {result.get("msg")}')

        count = 0
        for item in result.get('data', []):
            inst, created = Instrument.objects.update_or_create(
                inst_id=item['instId'],
                defaults={
                    'inst_type': inst_type,
                    'uly': item.get('uly', ''),
                    'base_ccy': item.get('baseCcy', ''),
                    'quote_ccy': item.get('quoteCcy', ''),
                    'ct_val': item.get('ctVal', ''),
                    'ct_mult': item.get('ctMult', ''),
                    'lot_sz': item.get('lotSz', ''),
                    'min_sz': item.get('minSz', ''),
                    'tick_sz': item.get('tickSz', ''),
                    'state': item.get('state', 'live'),
                    'is_active': True,
                }
            )
            count += 1
        logger.info(f'同步 {inst_type} 品种完成, 共 {count} 个')
        return count

    # ========== K线数据 ==========
    @staticmethod
    def fetch_klines(inst_id: str, bar: str = '1H', limit: int = 100,
                     before: str = '', after: str = '', is_history: bool = True) -> List[KLine]:
        """获取并存储K线数据"""
        client = get_okx_client()

        try:
            instrument = Instrument.objects.get(inst_id=inst_id)
        except Instrument.DoesNotExist:
            raise MarketDataUnavailable(f'品种 {inst_id} 不存在，请先同步')

        if is_history:
            result = client.get_history_candlesticks(
                inst_id=inst_id, bar=bar, limit=limit,
                after=after, before=before
            )
        else:
            result = client.get_candlesticks(
                inst_id=inst_id, bar=bar, limit=limit,
                after=after, before=before
            )

        if result['code'] != '0':
            raise MarketDataUnavailable(f'获取K线失败: {result.get("msg")}')

        klines = []
        for item in result.get('data', []):
            ts = datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.get_current_timezone())
            kline, created = KLine.objects.update_or_create(
                instrument=instrument,
                bar=bar,
                timestamp=ts,
                defaults={
                    'open': Decimal(str(item[1])),
                    'high': Decimal(str(item[2])),
                    'low': Decimal(str(item[3])),
                    'close': Decimal(str(item[4])),
                    'vol': Decimal(str(item[5])),
                    'vol_ccy': Decimal(str(item[6])),
                    'vol_ccy_quote': Decimal(str(item[7])),
                    'confirm': int(item[8]) if len(item) > 8 else 1,
                }
            )
            klines.append(kline)

        logger.info(f'获取 {inst_id} {bar} K线 {len(klines)} 条')
        return klines

    @staticmethod
    def get_klines_df(inst_id: str, bar: str = '1H', limit: int = 200) -> 'pd.DataFrame':
        """从数据库获取K线并返回DataFrame（用于因子计算）"""
        import pandas as pd
        klines = KLine.objects.filter(
            instrument__inst_id=inst_id, bar=bar
        ).order_by('timestamp')[:limit]

        if not klines:
            return pd.DataFrame()

        data = [{
            'timestamp': k.timestamp,
            'open': float(k.open),
            'high': float(k.high),
            'low': float(k.low),
            'close': float(k.close),
            'volume': float(k.vol),
            'vol_ccy': float(k.vol_ccy),
        } for k in klines]

        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    # ========== 行情快照 ==========
    @staticmethod
    def sync_ticker(inst_id: str) -> Ticker:
        """同步单个品种行情快照"""
        client = get_okx_client()
        result = client.get_ticker(inst_id=inst_id)
        if result['code'] != '0':
            raise MarketDataUnavailable(f'获取行情失败: {result.get("msg")}')

        data = result.get('data', [])
        if not data:
            raise MarketDataUnavailable(f'{inst_id} 无行情数据')

        item = data[0]
        try:
            instrument = Instrument.objects.get(inst_id=inst_id)
        except Instrument.DoesNotExist:
            instrument = Instrument.objects.create(inst_id=inst_id, inst_type='SPOT')

        ticker, _ = Ticker.objects.update_or_create(
            instrument=instrument,
            defaults={
                'last': Decimal(str(item.get('last', 0))),
                'open_24h': Decimal(str(item.get('open24h', 0))),
                'high_24h': Decimal(str(item.get('high24h', 0))),
                'low_24h': Decimal(str(item.get('low24h', 0))),
                'vol_24h': Decimal(str(item.get('vol24h', 0))),
                'vol_ccy_24h': Decimal(str(item.get('volCcy24h', 0))),
                'bid_px': Decimal(str(item.get('bidPx', 0))),
                'bid_sz': Decimal(str(item.get('bidSz', 0))),
                'ask_px': Decimal(str(item.get('askPx', 0))),
                'ask_sz': Decimal(str(item.get('askSz', 0))),
            }
        )
        return ticker

    # ========== 资金费率 ==========
    @staticmethod
    def sync_funding_rate(inst_id: str, limit: int = 100) -> int:
        """同步资金费率"""
        client = get_okx_client()
        result = client.get_funding_rate_history(inst_id=inst_id, limit=limit)
        if result['code'] != '0':
            raise MarketDataUnavailable(f'获取资金费率失败: {result.get("msg")}')

        try:
            instrument = Instrument.objects.get(inst_id=inst_id)
        except Instrument.DoesNotExist:
            instrument = Instrument.objects.create(inst_id=inst_id, inst_type='SWAP')

        count = 0
        for item in result.get('data', []):
            ft = datetime.fromtimestamp(int(item['fundingTime']) / 1000,
                                        tz=timezone.get_current_timezone())
            FundingRate.objects.update_or_create(
                instrument=instrument,
                funding_time=ft,
                defaults={
                    'funding_rate': Decimal(str(item['fundingRate'])),
                    'realized_rate': Decimal(str(item.get('realizedRate', item['fundingRate']))),
                }
            )
            count += 1
        return count
