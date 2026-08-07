"""行情数据 API 视图"""

from datetime import datetime

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from django.utils import timezone


class KLinePagination(PageNumberPagination):
    """K线接口默认返回更多数据以支撑图表展示"""
    page_size = 300
    page_size_query_param = 'page_size'
    max_page_size = 1000

from apps.market.models import Instrument, KLine, Ticker, FundingRate
from apps.market.serializers import (
    InstrumentSerializer, KLineSerializer,
    TickerSerializer, FundingRateSerializer,
)
from apps.market.services import MarketDataService
from apps.account.models import SystemConfig


class InstrumentViewSet(viewsets.ReadOnlyModelViewSet):
    """交易品种 API"""
    queryset = Instrument.objects.filter(is_active=True)
    serializer_class = InstrumentSerializer
    filterset_fields = ['inst_type', 'state']

    def get_queryset(self):
        """支持 keyword 模糊搜索品种ID（用于下拉选择组件）"""
        qs = Instrument.objects.filter(is_active=True)
        keyword = self.request.query_params.get('keyword', '').strip()
        if keyword:
            qs = qs.filter(inst_id__icontains=keyword.upper())
        inst_type = self.request.query_params.get('inst_type', '').strip()
        if inst_type:
            qs = qs.filter(inst_type=inst_type)
        return qs

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """手动同步交易品种"""
        inst_type = request.data.get('inst_type', 'SPOT')
        count = MarketDataService.sync_instruments(inst_type)
        return Response({'count': count, 'inst_type': inst_type})


class KLineViewSet(viewsets.ReadOnlyModelViewSet):
    """K线数据 API（自动按当前交易环境过滤，K线数据共享不过滤用户）"""

    queryset = KLine.objects.none()
    serializer_class = KLineSerializer
    filterset_fields = ['instrument__inst_id', 'bar', 'environment']
    pagination_class = KLinePagination

    def get_queryset(self):
        """自动过滤当前激活的交易环境"""
        try:
            env = SystemConfig.get_config(user=self.request.user).active_environment
        except Exception:
            env = 'demo'
        return KLine.objects.filter(environment=env)

    @action(detail=False, methods=['post'])
    def fetch(self, request):
        """手动拉取K线（支持翻页拉取更多历史数据）"""
        inst_id = request.data.get('inst_id')
        bar = request.data.get('bar', '1H')
        limit = request.data.get('limit', 300)
        is_history = request.data.get('is_history', True)

        if not inst_id:
            return Response({'error': 'inst_id is required'}, status=400)

        count = MarketDataService.fetch_klines_history(
            inst_id=inst_id, bar=bar, total=int(limit), user=request.user
        )
        env = MarketDataService._get_current_env(user=request.user)
        return Response({'count': count, 'inst_id': inst_id, 'bar': bar, 'environment': env})

    @action(detail=False, methods=['get'])
    def scroll(self, request):
        """按时间游标加载K线，支持左右滑动翻页。
        优先从数据库读取；数据库无数据时触发 Celery 后台异步拉取。
        参数:
          - inst_id: 品种ID (必填)
          - bar: K线周期 (必填)
          - before: 加载此时间戳之前的数据（向左滑动加载更旧数据）
          - after: 加载此时间戳之后的数据（向右滑动加载更新数据）
          - limit: 每次加载数量，默认500，最大1000
          - auto_fetch: 当数据库无数据时是否后台触发 OKX 拉取，默认 true
        返回:
          - results: K线数据列表
          - has_more: 是否还有更多数据
          - fetching: 是否已触发后台拉取（前端可据此提示用户稍后再滑动）
          - environment: 当前交易环境
        """
        inst_id = request.query_params.get('inst_id', '')
        bar = request.query_params.get('bar', '1H')
        before = request.query_params.get('before', '')
        after = request.query_params.get('after', '')
        limit = min(int(request.query_params.get('limit', 500)), 1000)
        auto_fetch = request.query_params.get('auto_fetch', 'true').lower() == 'true'

        if not inst_id:
            return Response({'error': 'inst_id is required'}, status=400)

        try:
            env = SystemConfig.get_config(user=request.user).active_environment
        except Exception:
            env = 'demo'

        qs = KLine.objects.filter(environment=env, instrument__inst_id=inst_id, bar=bar)

        if after:
            try:
                after_ts = datetime.fromtimestamp(int(after) / 1000, tz=timezone.get_current_timezone())
            except (ValueError, OSError):
                return Response({'error': 'invalid after timestamp'}, status=400)
            qs = qs.filter(timestamp__gt=after_ts).order_by('timestamp')
        elif before:
            try:
                before_ts = datetime.fromtimestamp(int(before) / 1000, tz=timezone.get_current_timezone())
            except (ValueError, OSError):
                return Response({'error': 'invalid before timestamp'}, status=400)
            qs = qs.filter(timestamp__lt=before_ts).order_by('-timestamp')
        else:
            qs = qs.order_by('-timestamp')

        if before:
            klines = list(qs[:limit])
            klines.reverse()
        else:
            klines = list(qs[:limit])
            klines = sorted(klines, key=lambda k: k.timestamp)

        fetching = False

        # 只在数据库完全无数据时，后台异步触发 OKX 拉取（不阻塞请求）
        if auto_fetch and len(klines) == 0:
            fetching = True
            from apps.market.tasks import async_fetch_klines_task
            async_fetch_klines_task.delay(
                inst_id=inst_id, bar=bar, total=500,
                before=str(before) if before else ''
            )

        # has_more 基于数据库实际状态
        has_more = False
        if before and klines:
            earliest = klines[0]
            has_more = KLine.objects.filter(
                environment=env, instrument__inst_id=inst_id, bar=bar,
                timestamp__lt=earliest.timestamp
            ).exists()
        elif after and klines:
            latest = klines[-1]
            has_more = KLine.objects.filter(
                environment=env, instrument__inst_id=inst_id, bar=bar,
                timestamp__gt=latest.timestamp
            ).exists()
        elif not before and not after and klines:
            latest = klines[-1]
            has_more = KLine.objects.filter(
                environment=env, instrument__inst_id=inst_id, bar=bar,
                timestamp__gt=latest.timestamp
            ).exists()

        serializer = KLineSerializer(klines, many=True)
        return Response({
            'results': serializer.data,
            'has_more': has_more,
            'fetching': fetching,
            'environment': env,
        })


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
