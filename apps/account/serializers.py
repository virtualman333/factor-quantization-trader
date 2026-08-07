from rest_framework import serializers
from .models import BalanceSnapshot, PositionSnapshot, NetValueHistory, OKXCredential, SystemConfig


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


