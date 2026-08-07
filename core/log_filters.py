import logging


class SkipStaticRequestsFilter(logging.Filter):
    """过滤静态资源请求日志，减少日志噪音。"""

    _STATIC_PREFIXES = ('/static/', '/media/', '/favicon.ico', '/robots.txt')

    def filter(self, record):
        request = getattr(record, 'request', None)
        if request is None:
            return True
        path = getattr(request, 'path', '')
        for prefix in self._STATIC_PREFIXES:
            if path.startswith(prefix) or path == prefix:
                return False
        return True
