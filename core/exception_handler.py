"""DRF 统一异常响应格式处理。

统一输出格式：
    {
        "code": <HTTP 状态码或业务错误码>,
        "message": <错误描述>,
        "data": <原始错误详情或 None>
    }
"""

from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException


def custom_exception_handler(exc, context):
    """将 DRF 异常转换为统一格式 {code, message, data}。"""
    response = exception_handler(exc, context)
    if response is None:
        return response

    status_code = response.status_code
    data = response.data

    if isinstance(data, dict) and 'detail' in data:
        message = data['detail']
        detail_data = None
    elif isinstance(data, (list, dict)):
        message = '请求参数错误' if status_code == 400 else '请求处理失败'
        detail_data = data
    else:
        message = str(data) or '请求处理失败'
        detail_data = None

    response.data = {
        'code': status_code,
        'message': message,
        'data': detail_data,
    }
    return response
