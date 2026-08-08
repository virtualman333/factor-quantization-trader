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
from apps.account.models import SystemConfig

logger = logging.getLogger(__name__)


class MarketDataService:
    """行情数据服务"""

    # ========== 交易品种 ==========
    @staticmethod
    def sync_instruments(inst_type: str = 'SPOT', user=None) -> int:
        """同步交易品种信息到本地数据库"""
        client = get_okx_client(user=user)
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
    def _get_current_env(user=None) -> str:
        """获取当前激活的交易环境"""
        try:
            return SystemConfig.get_config(user=user).active_environment
        except Exception:
            return 'demo'

    @staticmethod
    def _parse_kline_item(instrument, bar, item, user=None) -> KLine:
        """将 OKX 返回的单条 K 线数据解析并存入数据库（供少量单条写入场景使用）"""
        env = MarketDataService._get_current_env(user=user)
        ts = datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.get_current_timezone())
        kline, created = KLine.objects.update_or_create(
            instrument=instrument,
            environment=env,
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
        return kline

    @staticmethod
    def _bulk_save_klines(instrument, bar, raw_items, user=None) -> int:
        """批量解析并写入 K 线（高性能）。
        逐条 update_or_create 在大批量时极慢（300条~70s），
        改为 1 次 SELECT 查已存在 + 1 次 bulk_create。
        返回实际插入的条数。
        """
        if not raw_items:
            return 0
        env = MarketDataService._get_current_env(user=user)

        parsed = []
        for item in raw_items:
            ts = datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.get_current_timezone())
            parsed.append(KLine(
                instrument=instrument,
                environment=env,
                bar=bar,
                timestamp=ts,
                open=Decimal(str(item[1])),
                high=Decimal(str(item[2])),
                low=Decimal(str(item[3])),
                close=Decimal(str(item[4])),
                vol=Decimal(str(item[5])),
                vol_ccy=Decimal(str(item[6])) if len(item) > 6 else None,
                vol_ccy_quote=Decimal(str(item[7])) if len(item) > 7 else None,
                confirm=int(item[8]) if len(item) > 8 else 1,
            ))

        # 一次查询已存在的时间戳，避免重复写入
        ts_list = [p.timestamp for p in parsed]
        existing = set(
            KLine.objects.filter(
                instrument=instrument, environment=env, bar=bar,
                timestamp__in=ts_list
            ).values_list('timestamp', flat=True)
        )
        to_insert = [p for p in parsed if p.timestamp not in existing]
        if to_insert:
            KLine.objects.bulk_create(to_insert, batch_size=500)
        return len(to_insert)

    @staticmethod
    def fetch_klines(inst_id: str, bar: str = '1H', limit: int = 100,
                     before: str = '', after: str = '', is_history: bool = True,
                     user=None) -> List[KLine]:
        """获取并存储K线数据（单次请求）"""
        client = get_okx_client(user=user)

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

        env = MarketDataService._get_current_env(user=user)
        klines = []
        for item in result.get('data', []):
            klines.append(MarketDataService._parse_kline_item(instrument, bar, item, user=user))

        logger.info(f'[{env}] 获取 {inst_id} {bar} K线 {len(klines)} 条')
        return klines

    @staticmethod
    def fetch_klines_history(inst_id: str, bar: str = '1H',
                              total: int = 300, before: str = '', user=None) -> int:
        """递归从OKX拉取历史K线并存入数据库，直到达到目标数量或没有更多数据。
        每次API请求最多拉取300条（OKX历史K线接口上限），循环拉取直到满足 total 条。
        返回实际存入的条数。
        """
        client = get_okx_client(user=user)
        env = MarketDataService._get_current_env(user=user)
        try:
            instrument = Instrument.objects.get(inst_id=inst_id)
        except Instrument.DoesNotExist:
            raise MarketDataUnavailable(f'品种 {inst_id} 不存在，请先同步')

        total_stored = 0
        current_before = before  # 上一批数据中最旧的 timestamp（毫秒字符串），用于翻页
        remaining = total
        max_iterations = 20  # 安全上限，防止无限循环

        for _ in range(max_iterations):
            batch_limit = min(remaining, 300)
            result = client.get_history_candlesticks(
                inst_id=inst_id, bar=bar, limit=batch_limit,
                after='', before=current_before
            )

            if result['code'] != '0':
                raise MarketDataUnavailable(f'获取历史K线失败: {result.get("msg")}')

            items = result.get('data', [])
            if not items:
                break

            # 批量写入（单次 SELECT + bulk_create，避免逐条 update_or_create 性能瓶颈）
            inserted = MarketDataService._bulk_save_klines(instrument, bar, items, user=user)
            total_stored += len(items)
            remaining -= len(items)

            # 用本批次最旧的时间戳作为下一次翻页的 before 参数
            oldest_ts = items[-1][0]
            current_before = oldest_ts

            if remaining <= 0:
                break

            logger.info(f'  [{env}] 分页拉取 {inst_id} {bar}: 已拉取 {total_stored} 条，还需 {remaining} 条')

        logger.info(f'[{env}] 历史K线拉取完成: {inst_id} {bar}, 共 {total_stored} 条')
        return total_stored

    @staticmethod
    def get_klines_df(inst_id: str, bar: str = '1H', limit: int = 200, user=None) -> 'pd.DataFrame':
        """从数据库获取K线并返回DataFrame（用于因子计算，自动过滤当前环境）"""
        import pandas as pd
        env = MarketDataService._get_current_env(user=user)
        klines = KLine.objects.filter(
            environment=env, instrument__inst_id=inst_id, bar=bar
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

    @staticmethod
    def get_klines_cached(inst_id: str, bar: str = '1H', limit: int = 200,
                          min_required: int = 60, user=None) -> 'pd.DataFrame':
        """数据库优先读取K线；数据不足时后台异步拉取补齐并立即返回现有数据。
        用户无需感知拉取过程：有数据立即返回，无数据触发 Celery 后台拉取（下次读取即有）。
        """
        import pandas as pd

        env = MarketDataService._get_current_env(user=user)
        count = KLine.objects.filter(
            environment=env, instrument__inst_id=inst_id, bar=bar
        ).count()

        # 数据不足：触发异步拉取补齐（不阻塞请求），同时尝试同步拉取兜底
        if count < min_required:
            try:
                from apps.market.tasks import async_fetch_klines_task
                async_fetch_klines_task.delay(
                    inst_id=inst_id, bar=bar, total=max(limit, 200)
                )
                logger.info(f'[{env}] {inst_id} {bar} 数据不足({count}<{min_required})，已触发异步补齐')
            except Exception as e:
                logger.warning(f'异步补齐 {inst_id} {bar} 失败: {e}')

        return MarketDataService.get_klines_df(inst_id=inst_id, bar=bar, limit=limit, user=user)

    # ========== 行情快照 ==========
    @staticmethod
    def sync_ticker(inst_id: str, user=None) -> Ticker:
        """同步单个品种行情快照"""
        client = get_okx_client(user=user)
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
    def sync_funding_rate(inst_id: str, limit: int = 100, user=None) -> int:
        """同步资金费率"""
        client = get_okx_client(user=user)
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
