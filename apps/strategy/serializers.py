from rest_framework import serializers
from .models import StrategyConfig, FactorDefinition, SignalRecord, BacktestResult


class FactorDefinitionSerializer(serializers.ModelSerializer):
    factor_type_display = serializers.CharField(source='get_factor_type_display', read_only=True)

    class Meta:
        model = FactorDefinition
        fields = '__all__'


class SignalRecordSerializer(serializers.ModelSerializer):
    signal_display = serializers.CharField(source='get_signal_display', read_only=True)
    pos_side_display = serializers.CharField(source='get_pos_side_display', read_only=True)
    strategy_name = serializers.CharField(source='strategy.name', read_only=True)

    class Meta:
        model = SignalRecord
        fields = '__all__'


class StrategyConfigSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    strategy_type_display = serializers.CharField(source='get_strategy_type_display', read_only=True)
    td_mode_display = serializers.CharField(source='get_td_mode_display', read_only=True)
    signals_count = serializers.SerializerMethodField()

    class Meta:
        model = StrategyConfig
        fields = '__all__'

    def get_signals_count(self, obj):
        return obj.signals.count()



class BacktestResultSerializer(serializers.ModelSerializer):
    strategy_name = serializers.CharField(source='strategy.name', read_only=True)

    class Meta:
        model = BacktestResult
        fields = '__all__'
