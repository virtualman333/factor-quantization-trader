"""用户配额中间件：API 调用频率限制、策略数量上限检查"""

import time
import logging

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class UserQuotaMiddleware:
    """用户配额中间件：
    - 检查用户 API 调用频率是否超过配额限制
    - 创建策略/下单时检查数量上限
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user or not request.user.is_authenticated:
            return self.get_response(request)

        # 仅对 /api/ 路径进行配额检查
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        # 管理员不受配额限制
        if request.user.is_superuser:
            return self.get_response(request)

        try:
            from apps.account.models import UserQuota
            quota = UserQuota.get_quota(request.user)

            # 1. API 调用频率检查
            if not self._check_api_rate(request, quota):
                return JsonResponse({
                    'code': 429,
                    'message': f'API 调用频率超限（{quota.max_api_calls_per_minute}/分钟），请稍后再试',
                    'data': None,
                }, status=429)

            # 2. 策略创建上限检查
            if not self._check_strategy_limit(request, quota):
                return JsonResponse({
                    'code': 403,
                    'message': f'策略数量已达上限（{quota.max_strategies}），请删除旧策略后再创建',
                    'data': None,
                }, status=403)

            # 3. 下单频率检查
            if not self._check_order_limit(request, quota):
                return JsonResponse({
                    'code': 403,
                    'message': f'今日下单次数已达上限（{quota.max_orders_per_day}），请明日再试',
                    'data': None,
                }, status=403)

            # 4. K线查询数量检查
            if not self._check_kline_limit(request, quota):
                return JsonResponse({
                    'code': 403,
                    'message': f'K线查询数量超限（{quota.max_klines_per_request}条）',
                    'data': None,
                }, status=403)

        except Exception as e:
            logger.error(f'配额检查异常: {e}')

        return self.get_response(request)

    def _check_api_rate(self, request, quota):
        """检查 API 调用频率"""
        if quota.max_api_calls_per_minute <= 0:
            return True
        key = f'quota:api_rate:{request.user.id}'
        current_minute = int(time.time() / 60)
        data = cache.get(key, {'minute': current_minute, 'count': 0})
        if data['minute'] != current_minute:
            data = {'minute': current_minute, 'count': 0}
        data['count'] += 1
        cache.set(key, data, timeout=120)
        return data['count'] <= quota.max_api_calls_per_minute

    def _check_strategy_limit(self, request, quota):
        """检查策略创建上限（仅 POST /api/strategy/configs/ 且不含 pk 时）"""
        if not (request.method == 'POST' and 'strategy/configs' in request.path and not request.path.rstrip('/').split('/')[-1].isdigit()):
            return True
        from apps.strategy.models import StrategyConfig
        count = StrategyConfig.objects.filter(user=request.user).count()
        return count < quota.max_strategies

    def _check_order_limit(self, request, quota):
        """检查每日下单次数（仅 POST /api/orders/trades/ 时）"""
        if not (request.method == 'POST' and 'orders/trades' in request.path and request.path.rstrip('/').endswith('trades')):
            return True
        from apps.orders.models import TradeOrder
        from django.utils import timezone
        today = timezone.now().date()
        count = TradeOrder.objects.filter(
            user=request.user,
            created_at__date=today,
        ).count()
        return count < quota.max_orders_per_day

    def _check_kline_limit(self, request, quota):
        """检查 K 线查询数量（仅 POST /api/market/klines/fetch/ 时）"""
        if not ('market/klines/fetch' in request.path and request.method == 'POST'):
            return True
        limit = int(request.POST.get('limit', request.data.get('limit', 100)) if hasattr(request, 'data') else 100)
        return limit <= quota.max_klines_per_request
