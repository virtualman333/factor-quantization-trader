"""
OKX WebSocket 客户端封装
提供公共频道（行情）和私有频道（账户/订单）的实时数据订阅
"""

import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set

import websocket

from django.conf import settings

logger = logging.getLogger(__name__)


class OKXWebSocketBase:
    """WebSocket 基类：提供连接管理、自动重连、心跳保活"""

    def __init__(self, url: str, ping_interval: int = 20, reconnect_delay: float = 3.0):
        self.url = url
        self.ping_interval = ping_interval
        self.reconnect_delay = reconnect_delay
        self.ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {}  # channel -> [callbacks]

    def on_message(self, ws, message):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            # 跳过心跳响应
            if 'event' in data:
                event = data.get('event')
                if event in ('subscribe', 'unsubscribe', 'error'):
                    logger.info(f'WebSocket event: {event} - {data}')
                return

            # 分发到对应频道的回调
            if 'arg' in data and 'channel' in data['arg']:
                channel = data['arg']['channel']
                if channel in self._callbacks:
                    for cb in self._callbacks[channel]:
                        try:
                            cb(data)
                        except Exception as e:
                            logger.error(f'WebSocket callback error for {channel}: {e}')
        except Exception as e:
            logger.error(f'WebSocket message handling error: {e}')

    def on_error(self, ws, error):
        logger.error(f'WebSocket error: {error}')

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f'WebSocket closed: code={close_status_code}, msg={close_msg}')
        if self._running:
            logger.info(f'Reconnecting in {self.reconnect_delay}s...')
            time.sleep(self.reconnect_delay)
            self._connect()

    def on_open(self, ws):
        logger.info(f'WebSocket connected to {self.url}')
        self._subscribe_all()

    def _connect(self):
        """建立 WebSocket 连接"""
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        # 使用 ping_interval 自动心跳
        self.ws.run_forever(ping_interval=self.ping_interval, ping_timeout=10)

    def subscribe(self, channel: str, inst_id: str, callback: Callable):
        """订阅频道"""
        key = channel
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)
        logger.info(f'Subscribed to channel: {channel}, inst_id: {inst_id}')

    def unsubscribe(self, channel: str, inst_id: str):
        """取消订阅"""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            msg = json.dumps({
                'op': 'unsubscribe',
                'args': [{'channel': channel, 'instId': inst_id}],
            })
            self.ws.send(msg)
        if channel in self._callbacks:
            self._callbacks[channel] = []

    def _subscribe_all(self):
        """连接成功后重新订阅所有频道（子类实现）"""
        raise NotImplementedError

    def start(self):
        """启动 WebSocket（阻塞模式）"""
        if self._running:
            return
        self._running = True
        self._connect()

    def start_async(self):
        """启动 WebSocket（后台线程）"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._connect, daemon=True)
        self._thread.start()

    def stop(self):
        """停止 WebSocket"""
        self._running = False
        if self.ws:
            self.ws.close()


class OKXPublicWebSocket(OKXWebSocketBase):
    """公共频道 WebSocket：订阅行情数据"""

    PUBLIC_URL = 'wss://ws.okx.com:8443/ws/v5/public'

    def __init__(self):
        super().__init__(url=self.PUBLIC_URL)
        self._subscriptions: List[Dict] = []

    def subscribe_ticker(self, inst_id: str, callback: Callable):
        """订阅行情频道"""
        self._subscriptions.append({'channel': 'tickers', 'instId': inst_id})
        self.subscribe('tickers', inst_id, callback)

    def subscribe_candles(self, inst_id: str, bar: str, callback: Callable):
        """订阅K线频道"""
        args = {'channel': f'candle{bar}', 'instId': inst_id}
        self._subscriptions.append(args)
        self.subscribe(f'candle{bar}', inst_id, callback)

    def subscribe_orderbook(self, inst_id: str, depth: str = 'books', callback: Callable = None):
        """订阅深度频道"""
        args = {'channel': depth, 'instId': inst_id}
        self._subscriptions.append(args)
        self.subscribe(depth, inst_id, callback)

    def subscribe_trades(self, inst_id: str, callback: Callable):
        """订阅成交频道"""
        self._subscriptions.append({'channel': 'trades', 'instId': inst_id})
        self.subscribe('trades', inst_id, callback)

    def _subscribe_all(self):
        if not self._subscriptions:
            return
        msg = json.dumps({'op': 'subscribe', 'args': self._subscriptions})
        self.ws.send(msg)
        logger.info(f'Subscribed to {len(self._subscriptions)} public channels')


class OKXPrivateWebSocket(OKXWebSocketBase):
    """私有频道 WebSocket：订阅账户、订单、持仓数据"""

    PRIVATE_URL = 'wss://ws.okx.com:8443/ws/v5/private'

    def __init__(self, api_key: str = None, api_secret: str = None, passphrase: str = None):
        super().__init__(url=self.PRIVATE_URL)
        config = settings.OKX_CONFIG
        self.api_key = api_key or config['API_KEY']
        self.api_secret = api_secret or config['API_SECRET']
        self.passphrase = passphrase or config['PASSPHRASE']
        self._subscriptions: List[Dict] = []

    def on_open(self, ws):
        """连接后先登录"""
        # 登录认证
        import base64
        import hmac
        import datetime

        timestamp = str(int(time.time()))
        sign_str = timestamp + 'GET' + '/users/self/verify'
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                sign_str.encode('utf-8'),
                digestmod='sha256',
            ).digest()
        ).decode()

        login_msg = json.dumps({
            'op': 'login',
            'args': [{
                'apiKey': self.api_key,
                'passphrase': self.passphrase,
                'timestamp': timestamp,
                'sign': signature,
            }],
        })
        ws.send(login_msg)
        logger.info('WebSocket login sent')
        self._subscribe_all()

    def subscribe_account(self, callback: Callable):
        """订阅账户频道"""
        self._subscriptions.append({'channel': 'account', 'ccy': ''})
        self.subscribe('account', '', callback)

    def subscribe_positions(self, inst_type: str, inst_family: str, callback: Callable):
        """订阅持仓频道"""
        args = {'channel': 'positions', 'instType': inst_type}
        if inst_family:
            args['instFamily'] = inst_family
        self._subscriptions.append(args)
        self.subscribe('positions', inst_type, callback)

    def subscribe_orders(self, inst_type: str, inst_family: str = '', callback: Callable = None):
        """订阅订单频道"""
        args = {'channel': 'orders', 'instType': inst_type}
        if inst_family:
            args['instFamily'] = inst_family
        self._subscriptions.append(args)
        self.subscribe('orders', inst_type, callback)

    def _subscribe_all(self):
        if not self._subscriptions:
            return
        msg = json.dumps({'op': 'subscribe', 'args': self._subscriptions})
        self.ws.send(msg)
        logger.info(f'Subscribed to {len(self._subscriptions)} private channels')
