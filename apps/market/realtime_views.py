"""
实时行情 SSE 接口

- GET /api/market/realtime/stream/?subscribe=tickers:BTC-USDT,candle1H:BTC-USDT
  建立 SSE 长连接，推送 OKX 公共行情（ticker / candle）与连接状态事件。
  支持重复 subscribe 参数与逗号分隔多个订阅。
- GET /api/market/realtime/status/
  返回当前 OKX WS 连接状态与订阅列表。

鉴权：JWT（Authorization: Bearer <token>），SSE 使用 fetch 流式读取以便携带请求头。
"""

import json
import logging
import queue

from django.http import StreamingHttpResponse
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.realtime import (
    EVENT_HEARTBEAT,
    EVENT_STATUS,
    get_hub,
)
from apps.market.models import KLine

logger = logging.getLogger(__name__)

ALLOWED_BARS = {choice[0] for choice in KLine.BAR_CHOICES}


def parse_subscribe_params(raw_values) -> list:
    """解析 subscribe 参数，返回去重后的 'channel:instId' 列表"""
    keys = []
    for raw in raw_values:
        for token in raw.split(','):
            token = token.strip()
            if not token:
                continue
            if ':' not in token:
                raise ValueError(f'非法订阅格式: {token}，应为 channel:instId')
            channel, inst_id = (part.strip() for part in token.split(':', 1))
            if not channel or not inst_id:
                raise ValueError(f'非法订阅格式: {token}')
            if channel == 'tickers':
                keys.append(f'{channel}:{inst_id}')
            elif channel.startswith('candle') and channel[len('candle'):] in ALLOWED_BARS:
                keys.append(f'{channel}:{inst_id}')
            else:
                raise ValueError(f'不支持的频道: {channel}，仅支持 tickers 与 candle{"/".join(sorted(ALLOWED_BARS))}')

    seen = set()
    result = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            result.append(key)
    return result


def format_sse(event: str, payload: dict) -> str:
    return f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'


class RealtimeStreamView(APIView):
    """SSE 实时行情流"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = []

    def get(self, request):
        try:
            keys = parse_subscribe_params(request.query_params.getlist('subscribe'))
        except ValueError as e:
            return Response({'error': str(e)}, status=http_status.HTTP_400_BAD_REQUEST)

        hub = get_hub()
        client_queue = hub.register_client(keys)
        response = StreamingHttpResponse(
            self._event_stream(hub, client_queue),
            content_type='text/event-stream; charset=utf-8',
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        response['Connection'] = 'keep-alive'
        return response

    @staticmethod
    def _event_stream(hub, client_queue):
        try:
            # 先发送一次当前状态，前端可立即感知 OKX 连接情况
            yield format_sse(EVENT_STATUS, hub.status())
            while True:
                try:
                    event, payload = client_queue.get(timeout=15)
                    if event == EVENT_HEARTBEAT and payload.get('end'):
                        break
                    yield format_sse(event, payload)
                except queue.Empty:
                    yield ': ping\n\n'  # 保持连接活跃的注释行
        except GeneratorExit:
            pass
        except Exception:
            logger.exception('SSE stream error')
        finally:
            hub.unregister_client(client_queue)


class RealtimeStatusView(APIView):
    """实时通道状态查询"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_hub().status())
