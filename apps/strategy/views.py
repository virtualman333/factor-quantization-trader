"""策略引擎 API 视图"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.strategy.models import StrategyConfig, FactorDefinition, SignalRecord, BacktestResult
from apps.strategy.serializers import (
    StrategyConfigSerializer, FactorDefinitionSerializer,
    SignalRecordSerializer, BacktestResultSerializer,
)
from apps.strategy.services import StrategyService
from apps.strategy.factors import FactorEngine


class StrategyConfigViewSet(viewsets.ModelViewSet):
    """策略配置 CRUD API"""
    queryset = StrategyConfig.objects.all()
    serializer_class = StrategyConfigSerializer

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活策略"""
        strategy = self.get_object()
        strategy.status = 'active'
        strategy.save(update_fields=['status'])
        return Response({'status': 'activated'})

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """暂停策略"""
        strategy = self.get_object()
        strategy.status = 'paused'
        strategy.save(update_fields=['status'])
        return Response({'status': 'paused'})

    @action(detail=True, methods=['post'])
    def run_signals(self, request, pk=None):
        """手动运行信号生成"""
        strategy = self.get_object()
        signals = StrategyService.generate_signals(strategy)
        serializer = SignalRecordSerializer(signals, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def execute_signals(self, request, pk=None):
        """执行策略未执行信号"""
        strategy = self.get_object()
        signals = strategy.signals.filter(is_executed=False).order_by('-created_at')[:10]
        results = []
        for sig in signals:
            try:
                r = StrategyService.execute_signal(sig)
                results.append({'id': sig.id, 'success': True, 'result': r})
            except Exception as e:
                results.append({'id': sig.id, 'success': False, 'error': str(e)})
        return Response(results)

    @action(detail=True, methods=['post'])
    def backtest(self, request, pk=None):
        """运行回测"""
        strategy = self.get_object()
        from datetime import datetime, timedelta
        from django.utils import timezone

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        if not start_date or not end_date:
            # 默认回测最近30天
            now = timezone.now()
            start_date = (now - timedelta(days=30)).isoformat()
            end_date = now.isoformat()

        try:
            result = StrategyService.run_backtest(
                strategy,
                start_date=datetime.fromisoformat(start_date),
                end_date=datetime.fromisoformat(end_date),
            )
            serializer = BacktestResultSerializer(result)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class FactorDefinitionViewSet(viewsets.ReadOnlyModelViewSet):
    """因子定义 API"""
    queryset = FactorDefinition.objects.filter(is_active=True)
    serializer_class = FactorDefinitionSerializer

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """实时计算因子"""
        from apps.market.services import MarketDataService
        inst_id = request.data.get('inst_id')
        bar = request.data.get('bar', '1H')
        factor_names = request.data.get('factors', None)

        if not inst_id:
            return Response({'error': 'inst_id is required'}, status=400)

        # 先拉取最新K线
        MarketDataService.fetch_klines(inst_id=inst_id, bar=bar, limit=200)
        df = MarketDataService.get_klines_df(inst_id=inst_id, bar=bar, limit=200)

        if df.empty:
            return Response({'error': 'No K-line data'}, status=404)

        engine = FactorEngine(df)
        results = engine.calculate_all(factor_names)
        composite, signal = engine.get_composite_score()

        return Response({
            'inst_id': inst_id,
            'bar': bar,
            'composite_score': composite,
            'composite_signal': signal,
            'factors': {
                name: {
                    'value': r.value,
                    'score': r.score,
                    'signal': r.signal,
                }
                for name, r in results.items()
            }
        })


class SignalRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """交易信号 API"""
    queryset = SignalRecord.objects.all()
    serializer_class = SignalRecordSerializer
    filterset_fields = ['strategy', 'inst_id', 'signal', 'is_executed']

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行单个信号"""
        signal = self.get_object()
        try:
            result = StrategyService.execute_signal(signal)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)})


class BacktestResultViewSet(viewsets.ReadOnlyModelViewSet):
    """回测结果 API"""
    queryset = BacktestResult.objects.all()
    serializer_class = BacktestResultSerializer
    filterset_fields = ['strategy']
