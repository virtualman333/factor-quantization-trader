"""管理员专用 API：用户管理、配额管理、全局配置、统计面板"""

from django.contrib.auth.models import User
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.account.models import UserQuota, GlobalConfig
from apps.account.serializers import (
    UserQuotaSerializer, GlobalConfigSerializer,
    AdminUserSerializer, AdminUserStatsSerializer,
)


class IsSuperUser(permissions.BasePermission):
    """仅超级用户可访问"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """管理员用户管理 API"""
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        return User.objects.prefetch_related('quota').order_by('-date_joined')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取用户使用统计面板数据"""
        from apps.strategy.models import StrategyConfig, SignalRecord
        from apps.orders.models import TradeOrder

        users = User.objects.prefetch_related('quota').order_by('-date_joined')
        total_users = users.count()
        active_users = users.filter(is_active=True).count()
        total_strategies = StrategyConfig.objects.count()
        active_strategies = StrategyConfig.objects.filter(status='active').count()
        total_orders = TradeOrder.objects.count()
        total_signals = SignalRecord.objects.count()

        user_serializer = AdminUserSerializer(users, many=True)
        return Response({
            'total_users': total_users,
            'active_users': active_users,
            'total_strategies': total_strategies,
            'active_strategies': active_strategies,
            'total_orders': total_orders,
            'total_signals': total_signals,
            'user_details': user_serializer.data,
        })

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """启用/禁用用户"""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return Response({'id': user.id, 'is_active': user.is_active})

    @action(detail=True, methods=['post'])
    def toggle_staff(self, request, pk=None):
        """设置/取消管理员权限"""
        user = self.get_object()
        user.is_staff = not user.is_staff
        user.save(update_fields=['is_staff'])
        return Response({'id': user.id, 'is_staff': user.is_staff})


class UserQuotaViewSet(viewsets.ModelViewSet):
    """用户配额管理 API（仅管理员）"""
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]
    serializer_class = UserQuotaSerializer

    def get_queryset(self):
        return UserQuota.objects.select_related('user').all()

    @action(detail=False, methods=['get'])
    def by_user(self, request):
        """获取指定用户的配额 ?user_id=1"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id is required'}, status=400)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': '用户不存在'}, status=404)
        quota = UserQuota.get_quota(user)
        serializer = self.get_serializer(quota)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def batch_update(self, request):
        """批量更新所有用户配额"""
        defaults = {
            'max_strategies': request.data.get('max_strategies'),
            'max_orders_per_day': request.data.get('max_orders_per_day'),
            'max_api_calls_per_minute': request.data.get('max_api_calls_per_minute'),
            'is_trading_enabled': request.data.get('is_trading_enabled'),
        }
        defaults = {k: v for k, v in defaults.items() if v is not None}
        count = UserQuota.objects.update(**defaults)
        return Response({'updated': count})


class GlobalConfigViewSet(viewsets.ViewSet):
    """系统级全局配置（仅管理员）"""
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]

    def list(self, request):
        config = GlobalConfig.get_config()
        return Response(GlobalConfigSerializer(config).data)

    def create(self, request):
        config = GlobalConfig.get_config()
        serializer = GlobalConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminConfigView(APIView):
    """管理员概览：同时返回全局配置 + 当前用户配额"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        is_admin = request.user.is_superuser or request.user.is_staff
        data = {
            'is_admin': is_admin,
            'user_quota': None,
            'global_config': None,
        }
        quota = UserQuota.get_quota(request.user)
        data['user_quota'] = UserQuotaSerializer(quota).data
        if is_admin:
            data['global_config'] = GlobalConfigSerializer(GlobalConfig.get_config()).data
        return Response(data)
