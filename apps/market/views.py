"""行情数据 API 视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.market.models import Instrument, KLine, Ticker, FundingRate
from apps.market.serializers import (
    InstrumentSerializer, KLineSerializer,
    TickerSerializer, FundingRateSerializer,
)
from apps.market.services import MarketDataService


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    """交易品种 API"""
    queryset = Instrument.objects.filter(is_active=True)
    serializer_class = InstrumentSerializer
    filterset_fields = ['inst_type', 'state']

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """手动同步交易品种"""
        inst_type = request.data.get('inst_type', 'SPOT')
        count = MarketDataService.sync_instruments(inst_type)
        return Response({'count': count, 'inst_type': inst_type})


class KLineViewSet(viewsets.ReadOnlyModelViewSet):
    """K线数据 API"""
    queryset = KLine.objects.all()
    serializer_class = KLineSerializer
    filterset_fields = ['instrument__inst_id', 'bar']

    @action(detail=False, methods=['post'])
    def fetch(self, request):
        """手动拉取K线"""
        inst_id = request.data.get('inst_id')
        bar = request.data.get('bar', '1H')
        limit = request.data.get('limit', 100)
        is_history = request.data.get('is_history', True)

        if not inst_id:
            return Response({'error': 'inst_id is required'}, status=400)

        klines = MarketDataService.fetch_klines(
            inst_id=inst_id, bar=bar, limit=limit, is_history=is_history
        )
        serializer = KLineSerializer(klines, many=True)
        return Response(serializer.data)


class TickerViewSet(viewsets.ReadOnlyModelViewSet):
    """行情快照 API"""
    queryset = Ticker.objects.all()
    serializer_class = TickerSerializer
    filterset_fields = ['instrument__inst_id', 'instrument__inst_type']

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """手动刷新行情"""
        inst_id = request.data.get('inst_id')
        if not inst_id:
            return Response({'error': 'inst_id is required'}, status=400)

        ticker = MarketDataService.sync_ticker(inst_id)
        serializer = TickerSerializer(ticker)
        return Response(serializer.data)


class FundingRateViewSet(viewsets.ReadOnlyModelViewSet):
    """资金费率 API"""
    queryset = FundingRate.objects.all()
    serializer_class = FundingRateSerializer
    filterset_fields = ['instrument__inst_id']
