"""认证相关限流器。
"""

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """登录接口限流，防止暴力破解。"""

    rate = '5/minute'
    scope = 'login'
