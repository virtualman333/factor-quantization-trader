"""全局 API 错误中间件。

捕获 Django 原生 404/500 等未由 DRF 处理的异常，统一返回 JSON 格式。
"""

from django.http import JsonResponse
from django.conf import settings


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
