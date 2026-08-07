from django.contrib.auth.models import User
from rest_framework import serializers
from .models import (
    BalanceSnapshot, PositionSnapshot, NetValueHistory,
    OKXCredential, SystemConfig, UserQuota, GlobalConfig,
)


class BalanceSnapshotSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = BalanceSnapshot
        fields = '__all__'


class PositionSnapshotSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = PositionSnapshot
        fields = '__all__'


class NetValueHistorySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = NetValueHistory
        fields = '__all__'


class OKXCredentialSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = OKXCredential
        fields = ['id', 'user', 'username', 'name', 'api_key', 'api_secret',
                  'passphrase', 'flag', 'is_active', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_secret': {'write_only': True},
            'passphrase': {'write_only': True},
        }


class SystemConfigSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = SystemConfig
        fields = ['id', 'user', 'username', 'active_environment', 'updated_at']


class UserQuotaSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserQuota
        fields = '__all__'


class GlobalConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalConfig
        fields = '__all__'


class AdminUserSerializer(serializers.ModelSerializer):
    """管理员查看用户列表时使用的序列化器"""
    strategy_count = serializers.SerializerMethodField()
    order_count = serializers.SerializerMethodField()
    quota = UserQuotaSerializer(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login', 'strategy_count', 'order_count', 'quota',
        ]

    def get_strategy_count(self, obj):
        from apps.strategy.models import StrategyConfig
        return StrategyConfig.objects.filter(user=obj).count()

    def get_order_count(self, obj):
        from apps.orders.models import TradeOrder
        return TradeOrder.objects.filter(user=obj).count()


class AdminUserStatsSerializer(serializers.Serializer):
    """用户统计面板序列化器"""
    total_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    total_strategies = serializers.IntegerField()
    active_strategies = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_signals = serializers.IntegerField()
    user_details = AdminUserSerializer(many=True)
