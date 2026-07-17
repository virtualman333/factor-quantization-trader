from rest_framework import serializers
from .models import BalanceSnapshot, PositionSnapshot, NetValueHistory, OKXCredential, SystemConfig



class BalanceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceSnapshot
        fields = '__all__'


class PositionSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionSnapshot
        fields = '__all__'


class NetValueHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = NetValueHistory
        fields = '__all__'


class OKXCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = OKXCredential
        fields = ['id', 'name', 'api_key', 'api_secret', 'passphrase', 'flag', 'is_active', 'created_at', 'updated_at']


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = ['id', 'active_environment', 'updated_at']


