from rest_framework import serializers
from .models import Instrument, KLine, Ticker, FundingRate


class InstrumentSerializer(serializers.ModelSerializer):
    inst_type_display = serializers.CharField(source='get_inst_type_display', read_only=True)

    class Meta:
        model = Instrument
        fields = '__all__'


class KLineSerializer(serializers.ModelSerializer):
    inst_id = serializers.CharField(source='instrument.inst_id', read_only=True)
    bar_display = serializers.CharField(source='get_bar_display', read_only=True)

    class Meta:
        model = KLine
        fields = ['id', 'inst_id', 'bar', 'bar_display', 'timestamp',
                  'open', 'high', 'low', 'close', 'vol', 'vol_ccy', 'confirm']
        read_only_fields = fields


class TickerSerializer(serializers.ModelSerializer):
    inst_id = serializers.CharField(source='instrument.inst_id', read_only=True)
    inst_type = serializers.CharField(source='instrument.inst_type', read_only=True)

    class Meta:
        model = Ticker
        fields = '__all__'


class FundingRateSerializer(serializers.ModelSerializer):
    inst_id = serializers.CharField(source='instrument.inst_id', read_only=True)

    class Meta:
        model = FundingRate
        fields = '__all__'
