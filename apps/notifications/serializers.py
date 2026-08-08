from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = Notification
        fields = '__all__'
        extra_kwargs = {'user': {'read_only': True}}


class NotificationSummarySerializer(serializers.Serializer):
    """未读数统计。"""
    total_unread = serializers.IntegerField()
    by_type = serializers.DictField(child=serializers.IntegerField())
    by_level = serializers.DictField(child=serializers.IntegerField())
