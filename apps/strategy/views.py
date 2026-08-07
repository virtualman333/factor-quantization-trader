"""策略引擎 API 视图"""

import re

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.strategy.models import StrategyConfig, FactorDefinition, SignalRecord, BacktestResult
from apps.strategy.serializers import (
    StrategyConfigSerializer, FactorDefinitionSerializer,
    SignalRecordSerializer, BacktestResultSerializer,
)
from apps.strategy.services import StrategyService, StrategyError
from apps.strategy.factors import FactorEngine
from core.okx_client import get_okx_client


class StrategyConfigViewSet(viewsets.ModelViewSet):
    """策略配置 CRUD API"""
    queryset = StrategyConfig.objects.all()
    serializer_class = StrategyConfigSerializer

    def get_queryset(self):
        """支持列表筛选：keyword(名称模糊)、strategy_type、inst_type、status、direction"""
        qs = super().get_queryset()
        params = self.request.query_params
        keyword = params.get('keyword')
        if keyword:
            qs = qs.filter(name__icontains=keyword.strip())
        for field in ('strategy_type', 'inst_type', 'status', 'direction'):
            val = params.get(field)
            if val:
                qs = qs.filter(**{field: val})
        return qs

    @action(detail=False, methods=['get'])
    def instruments(self, request):
        """获取 OKX 交易产品列表（支持下拉选交易对）"""
        inst_type = request.query_params.get('inst_type', 'SWAP')
        client = get_okx_client()
        try:
            result = client.get_instruments(inst_type=inst_type)
            data = result.get('data', [])
            # 过滤仅可交易、状态为 live 的产品
            items = [
                {
                    'instId': item.get('instId'),
                    'instType': item.get('instType'),
                    'baseCcy': item.get('baseCcy', ''),
                    'quoteCcy': item.get('quoteCcy', ''),
                    'state': item.get('state', ''),
                    'label': item.get('instId'),
                    'value': item.get('instId'),
                }
                for item in data
                if item.get('state') == 'live' and item.get('instId')
            ]
            return Response({'inst_type': inst_type, 'instruments': items})
        except Exception as e:
            # 兜底：返回常见 U 本位永续合约
            fallback = [
                'BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP',
                'XRP-USDT-SWAP', 'DOGE-USDT-SWAP', 'LTC-USDT-SWAP',
                'BNB-USDT-SWAP', 'ADA-USDT-SWAP', 'AVAX-USDT-SWAP',
                'MATIC-USDT-SWAP', 'LINK-USDT-SWAP', 'UNI-USDT-SWAP',
            ]
            items = [{'label': s, 'value': s, 'instType': inst_type} for s in fallback]
            return Response({
                'inst_type': inst_type,
                'instruments': items,
                'fallback': True,
                'error': str(e),
            })

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
        from django.utils.dateparse import parse_datetime, parse_date

        def _parse_dt(value, is_end=False):
            """解析前端传入的日期/时间字符串。

            前端日期选择器可能只传 YYYY-MM-DD（纯日期）。若 end_date 缺省时间，
            应取当天 23:59:59 而非 00:00，否则会把当天所有 K 线数据过滤掉。
            注意：新版 Django 的 parse_datetime 对纯日期会返回 00:00，因此先以
            正则识别纯日期，确保 end 能取到当天结束时刻。
            """
            if not value:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                    d = parse_date(value)
                    if d is not None:
                        if is_end:
                            return datetime(d.year, d.month, d.day, 23, 59, 59, 999999)
                        return datetime(d.year, d.month, d.day, 0, 0, 0, 0)
                dt = parse_datetime(value)
                if dt is not None:
                    return dt
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    return None
            return None

        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')

        start_dt = _parse_dt(start_date, is_end=False)
        end_dt = _parse_dt(end_date, is_end=True)

        if not start_dt or not end_dt:
            # 默认回测最近30天
            now = timezone.now()
            end_dt = now
            start_dt = now - timedelta(days=30)

        # 统一为带时区的时间，避免 naive datetime 警告
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)

        try:
            result = StrategyService.run_backtest(
                strategy,
                start_date=start_dt,
                end_date=end_dt,
            )
            serializer = BacktestResultSerializer(result)
            return Response(serializer.data)
        except StrategyError as e:
            return Response({'error': str(e)}, status=400)
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
