"""
实时行情中枢 (SSE 服务端)

职责：
1. 维护两条 OKX 公共行情 WebSocket 长连接（asyncio + websockets 库）：
   - public 端点：tickers 频道
   - business 端点：candle{bar} 频道（OKX 已将 K 线频道迁移到 business WS）
2. 按订阅计数动态 subscribe / unsubscribe tickers、candle{bar} 频道
3. 将归一化后的行情消息推送给所有 SSE 客户端（进程内队列 pub/sub）
4. 节流落库：Ticker 快照、KLine 最新 K 线（demo/live 双环境同步）

说明：
- 当前实现为进程内 pub/sub，适用于单进程部署（start.bat 单 worker 场景）。
- 多进程/多 worker 部署时，需要将广播层替换为 Redis pub/sub：
  只有持有 OKX WS 连接的进程连接 OKX，其余进程通过 Redis 频道转发 SSE 消息。
- 行情数据为公开数据（demo/live 共享同一行情），因此 K 线同时写入两个环境，
  保证切换环境后图表数据仍然连续。
"""

import asyncio
import json
import logging
import queue
import threading
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Set

import websockets

from django.db import connection as db_connection
from django.utils import timezone

logger = logging.getLogger(__name__)

OKX_PUBLIC_WS_URL = 'wss://ws.okx.com:8443/ws/v5/public'
OKX_BUSINESS_WS_URL = 'wss://ws.okx.com:8443/ws/v5/business'
RECONNECT_DELAY = 3.0

# SSE 事件类型
EVENT_TICKER = 'ticker'
EVENT_CANDLE = 'candle'
EVENT_STATUS = 'status'
EVENT_HEARTBEAT = 'heartbeat'

# 持久化节流（秒）：同一标的写入间隔，避免高频行情压垮数据库
WRITE_THROTTLE = {'ticker': 3.0, 'candle': 1.0}


def _to_decimal(value):
    """安全转换为 Decimal；空值返回 None"""
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _channel_key(channel: str, inst_id: str) -> str:
    return f'{channel}:{inst_id}'


def _endpoint_for_key(key: str) -> str:
    """根据订阅 key 返回对应 OKX WS 端点类型"""
    channel = key.split(':', 1)[0]
    return 'business' if channel.startswith('candle') else 'public'


class MarketRealtimeHub:
    """OKX 公共行情 → SSE 广播中枢（单例）"""

    def __init__(self):
        self._lock = threading.RLock()
        self._refcounts: Dict[str, int] = {}  # channel:instId -> 订阅计数
        self._clients: Dict[queue.Queue, Set[str]] = {}  # SSE 客户端队列 -> 订阅集合

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._ws: Dict[str, object] = {}  # endpoint kind -> websocket 连接
        self._connected_endpoints: Set[str] = set()
        self._stopped = False

        self._write_queue: queue.Queue = queue.Queue(maxsize=2000)
        self._last_write_at: Dict[str, float] = {}

    # ==================== 对外接口（Django 线程调用） ====================

    def status(self) -> dict:
        with self._lock:
            needed = {_endpoint_for_key(key) for key in self._refcounts}
            return {
                # 有订阅的端点全部连通才算 connected；无订阅时视为通道就绪
                'connected': needed <= self._connected_endpoints,
                'subscriptions': sorted(self._refcounts.keys()),
                'clients': len(self._clients),
                'endpoints': sorted(self._connected_endpoints),
            }

    def register_client(self, keys) -> queue.Queue:
        """注册一个 SSE 客户端，返回其消息队列"""
        client_queue = queue.Queue(maxsize=500)
        with self._lock:
            self._clients[client_queue] = set(keys)
        for key in keys:
            self._incr(key)
        self._ensure_running()
        return client_queue

    def unregister_client(self, client_queue):
        """SSE 客户端断开：释放其订阅并唤醒读取线程"""
        with self._lock:
            keys = self._clients.pop(client_queue, None)
        if keys:
            for key in keys:
                self._decr(key)
        try:
            client_queue.put_nowait((EVENT_HEARTBEAT, {'end': True}))
        except queue.Full:
            pass

    def close(self):
        """关闭整个中枢（进程退出时调用）"""
        self._stopped = True
        loop = self._loop
        if loop and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                pass

    # ==================== 订阅计数 ====================

    def _incr(self, key: str):
        with self._lock:
            self._refcounts[key] = self._refcounts.get(key, 0) + 1
            if (
                self._refcounts[key] == 1
                and _endpoint_for_key(key) in self._connected_endpoints
            ):
                self._schedule_ws(self._ws_subscribe(key))

    def _decr(self, key: str):
        with self._lock:
            remaining = self._refcounts.get(key, 0) - 1
            if remaining <= 0:
                self._refcounts.pop(key, None)
                if _endpoint_for_key(key) in self._connected_endpoints:
                    self._schedule_ws(self._ws_unsubscribe(key))
            else:
                self._refcounts[key] = remaining

    def _current_keys(self):
        with self._lock:
            return list(self._refcounts.keys())

    # ==================== 线程与事件循环 ====================

    def _ensure_running(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stopped = False
            self._thread = threading.Thread(
                target=self._run_loop, name='okx-realtime-hub', daemon=True
            )
            self._thread.start()
            if not self._writer_thread or not self._writer_thread.is_alive():
                self._writer_thread = threading.Thread(
                    target=self._run_writer, name='okx-realtime-writer', daemon=True
                )
                self._writer_thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception:
            logger.exception('realtime hub loop crashed')
        finally:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None

    async def _main(self):
        """同时维护 public（tickers）与 business（candles）两条连接"""
        await asyncio.gather(
            self._connection_loop('public', OKX_PUBLIC_WS_URL),
            self._connection_loop('business', OKX_BUSINESS_WS_URL),
        )

    async def _connection_loop(self, kind: str, url: str):
        while not self._stopped:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    max_size=2 ** 20,
                ) as ws:
                    self._set_endpoint(kind, ws)
                    await self._subscribe_current(kind)
                    async for raw in ws:
                        if self._stopped:
                            break
                        try:
                            data = json.loads(raw)
                        except (TypeError, ValueError):
                            continue
                        self._handle_message(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning('OKX WS [%s] error: %s', kind, e)
            finally:
                self._clear_endpoint(kind)
            if not self._stopped:
                await asyncio.sleep(RECONNECT_DELAY)

    def _schedule_ws(self, coro):
        loop = self._loop
        if loop is None or loop.is_closed():
            try:
                coro.close()
            except Exception:
                pass
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            try:
                coro.close()
            except Exception:
                pass

    async def _ws_subscribe(self, key: str):
        ws = self._ws.get(_endpoint_for_key(key))
        if ws is None:
            return
        channel, inst_id = key.split(':', 1)
        try:
            await ws.send(json.dumps({
                'op': 'subscribe',
                'args': [{'channel': channel, 'instId': inst_id}],
            }))
            logger.info('OKX WS subscribe: %s', key)
        except Exception as e:
            logger.warning('OKX WS subscribe failed %s: %s', key, e)

    async def _ws_unsubscribe(self, key: str):
        ws = self._ws.get(_endpoint_for_key(key))
        if ws is None:
            return
        channel, inst_id = key.split(':', 1)
        try:
            await ws.send(json.dumps({
                'op': 'unsubscribe',
                'args': [{'channel': channel, 'instId': inst_id}],
            }))
        except Exception as e:
            logger.warning('OKX WS unsubscribe failed %s: %s', key, e)

    async def _subscribe_current(self, kind: str):
        for key in self._current_keys():
            if _endpoint_for_key(key) == kind:
                await self._ws_subscribe(key)

    def _set_endpoint(self, kind: str, ws):
        with self._lock:
            existed = kind in self._connected_endpoints
            self._ws[kind] = ws
            self._connected_endpoints.add(kind)
            changed = not existed
        if changed:
            logger.info('OKX WS [%s] connected', kind)
            self._broadcast_status()

    def _clear_endpoint(self, kind: str):
        with self._lock:
            existed = kind in self._connected_endpoints
            self._ws.pop(kind, None)
            self._connected_endpoints.discard(kind)
            changed = existed
        if changed:
            logger.info('OKX WS [%s] disconnected', kind)
            self._broadcast_status()

    def _broadcast_status(self):
        """向所有 SSE 客户端广播连接状态（不按频道过滤）"""
        frame = (EVENT_STATUS, self.status())
        with self._lock:
            clients = list(self._clients)
        for client_queue in clients:
            try:
                client_queue.put_nowait(frame)
            except queue.Full:
                pass

    # ==================== 消息处理与广播 ====================

    def _handle_message(self, data: dict):
        if 'event' in data:
            return
        arg = data.get('arg') or {}
        channel = arg.get('channel', '')
        inst_id = arg.get('instId', '')
        if not channel or not inst_id:
            return

        items = data.get('data') or []
        for item in items:
            if channel == 'tickers':
                payload = self._normalize_ticker(inst_id, item)
                self._broadcast(_channel_key(channel, inst_id), EVENT_TICKER, payload)
                self._enqueue_write('ticker', payload)
            elif channel.startswith('candle'):
                bar = channel[len('candle'):]
                payload = self._normalize_candle(inst_id, bar, item)
                payload['channel'] = channel
                self._broadcast(_channel_key(channel, inst_id), EVENT_CANDLE, payload)
                self._enqueue_write('candle', payload)

    def _broadcast(self, key: str, event: str, payload: dict):
        frame = (event, payload)
        with self._lock:
            clients = list(self._clients.items())
        for client_queue, keys in clients:
            if key not in keys:
                continue
            try:
                client_queue.put_nowait(frame)
            except queue.Full:
                pass  # 客户端消费慢时丢弃旧消息，保持流不阻塞

    @staticmethod
    def _normalize_ticker(inst_id: str, item: dict) -> dict:
        return {
            'inst_id': inst_id,
            'last': item.get('last'),
            'open_24h': item.get('open24h'),
            'high_24h': item.get('high24h'),
            'low_24h': item.get('low24h'),
            'vol_24h': item.get('vol24h'),
            'vol_ccy_24h': item.get('volCcy24h'),
            'bid_px': item.get('bidPx'),
            'bid_sz': item.get('bidSz'),
            'ask_px': item.get('askPx'),
            'ask_sz': item.get('askSz'),
            'ts': item.get('ts'),
        }

    @staticmethod
    def _normalize_candle(inst_id: str, bar: str, item: list) -> dict:
        return {
            'inst_id': inst_id,
            'bar': bar,
            'timestamp': int(item[0]),
            'open': item[1],
            'high': item[2],
            'low': item[3],
            'close': item[4],
            'vol': item[5],
            'vol_ccy': item[6] if len(item) > 6 else '0',
            'vol_ccy_quote': item[7] if len(item) > 7 else '0',
            'confirm': int(item[8]) if len(item) > 8 else 1,
        }

    # ==================== 持久化（独立写入线程 + 节流） ====================

    def _enqueue_write(self, kind: str, payload: dict):
        try:
            self._write_queue.put_nowait((kind, payload))
        except queue.Full:
            pass

    def _run_writer(self):
        while True:
            try:
                kind, payload = self._write_queue.get(timeout=1)
            except queue.Empty:
                continue

            throttle_key = f"{kind}:{payload.get('inst_id')}:{payload.get('bar', '')}"
            now = time.monotonic()
            if now - self._last_write_at.get(throttle_key, 0) < WRITE_THROTTLE[kind]:
                continue
            self._last_write_at[throttle_key] = now

            try:
                if kind == 'ticker':
                    self._persist_ticker(payload)
                elif kind == 'candle':
                    self._persist_candle(payload)
            except Exception:
                logger.exception('realtime persist failed: %s %s', kind, payload.get('inst_id'))
            finally:
                try:
                    db_connection.close()
                except Exception:
                    pass

    @staticmethod
    def _persist_ticker(payload: dict):
        from apps.market.models import Instrument, Ticker

        instrument, _ = Instrument.objects.get_or_create(
            inst_id=payload['inst_id'],
            defaults={'inst_type': 'SPOT', 'is_active': True},
        )
        Ticker.objects.update_or_create(
            instrument=instrument,
            defaults={
                'last': _to_decimal(payload.get('last')),
                'open_24h': _to_decimal(payload.get('open_24h')),
                'high_24h': _to_decimal(payload.get('high_24h')),
                'low_24h': _to_decimal(payload.get('low_24h')),
                'vol_24h': _to_decimal(payload.get('vol_24h')),
                'vol_ccy_24h': _to_decimal(payload.get('vol_ccy_24h')),
                'bid_px': _to_decimal(payload.get('bid_px')),
                'bid_sz': _to_decimal(payload.get('bid_sz')),
                'ask_px': _to_decimal(payload.get('ask_px')),
                'ask_sz': _to_decimal(payload.get('ask_sz')),
            },
        )

    @staticmethod
    def _persist_candle(payload: dict):
        from apps.market.models import Instrument, KLine

        instrument, _ = Instrument.objects.get_or_create(
            inst_id=payload['inst_id'],
            defaults={'inst_type': 'SPOT', 'is_active': True},
        )
        ts = datetime.fromtimestamp(
            payload['timestamp'] / 1000, tz=timezone.get_current_timezone()
        )
        defaults = {
            'open': Decimal(str(payload['open'])),
            'high': Decimal(str(payload['high'])),
            'low': Decimal(str(payload['low'])),
            'close': Decimal(str(payload['close'])),
            'vol': Decimal(str(payload['vol'])),
            'vol_ccy': Decimal(str(payload['vol_ccy'])),
            'vol_ccy_quote': Decimal(str(payload['vol_ccy_quote'])),
            'confirm': payload['confirm'],
        }
        # 公共行情 demo/live 一致，双环境写入保证切换后数据连续
        for env in ('demo', 'live'):
            KLine.objects.update_or_create(
                instrument=instrument,
                environment=env,
                bar=payload['bar'],
                timestamp=ts,
                defaults=defaults,
            )


_hub: Optional[MarketRealtimeHub] = None
_hub_lock = threading.Lock()


def get_hub() -> MarketRealtimeHub:
    """获取全局唯一的实时行情中枢"""
    global _hub
    if _hub is None:
        with _hub_lock:
            if _hub is None:
                _hub = MarketRealtimeHub()
    return _hub
