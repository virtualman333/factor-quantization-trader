from rest_framework import serializers
from .models import TradeOrder, OrderLog, OrderTemplate


class OrderTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderTemplate
        fields = '__all__'
        extra_kwargs = {'user': {'read_only': True}}


class OrderLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = OrderLog
        fields = '__all__'


class TradeOrderSerializer(serializers.ModelSerializer):
    side_display = serializers.CharField(source='get_side_display', read_only=True)
    ord_type_display = serializers.CharField(source='get_ord_type_display', read_only=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    logs = OrderLogSerializer(many=True, read_only=True)

    class Meta:
        model = TradeOrder
        fields = '__all__'
        extra_kwargs = {'user': {'read_only': True}}
