"""全局 API 错误中间件 & 请求日志中间件。

捕获 Django 原生 404/500 等未由 DRF 处理的异常，统一返回 JSON 格式。
记录 API 请求耗时与状态码。
"""

import logging
import time

from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger('api.request')


class ApiErrorMiddleware:
    """对 /api/ 路径下的非 JSON 错误响应统一包装为 {code, message, data}。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/api/'):
            return response
        if response.status_code < 400:
            return response
        if isinstance(response, JsonResponse):
            return response
        content_type = response.get('Content-Type', '')
        if 'application/json' in content_type:
            return response
        return JsonResponse(
            {
                'code': response.status_code,
                'message': response.reason_phrase or '请求处理失败',
                'data': None,
            },
            status=response.status_code,
        )

    def process_exception(self, request, exception):
        """兜底：将 /api/ 路径下的未处理异常转为 500 JSON。"""
        if not request.path.startswith('/api/'):
            return None
        return JsonResponse(
            {
                'code': 500,
                'message': '服务器内部错误',
                'data': str(exception) if settings.DEBUG else None,
            },
            status=500,
        )


class RequestLogMiddleware:
    """记录所有 API 请求的方法、路径、状态码和耗时。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = (time.time() - start_time) * 1000
        status_code = response.status_code
        method = request.method
        path = request.path
        user = getattr(request, 'user', None)
        username = user.username if user and user.is_authenticated else 'anonymous'
        client_ip = self._get_client_ip(request)
        if status_code >= 500:
            logger.error(
                '%s %s | %s | %s | %.1fms | client=%s',
                method, path, status_code, username, duration, client_ip,
            )
        elif status_code >= 400:
            logger.warning(
                '%s %s | %s | %s | %.1fms | client=%s',
                method, path, status_code, username, duration, client_ip,
            )
        else:
            logger.info(
                '%s %s | %s | %s | %.1fms | client=%s',
                method, path, status_code, username, duration, client_ip,
            )
        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
