"""仪表盘聚合数据 API"""
from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.strategy.services import StrategyService


class DashboardViewSet(viewsets.ViewSet):
    """仪表盘聚合数据"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def strategy_ranking(self, request):
        """策略收益排行"""
        limit = int(request.query_params.get('limit', 10))
        data = StrategyService.strategy_ranking(user=request.user, limit=limit)
        return Response({'results': data})

    @action(detail=False, methods=['get'])
    def factor_heatmap(self, request):
        """因子热力图"""
        n = int(request.query_params.get('n', 200))
        data = StrategyService.factor_heatmap(user=request.user, n_signals=n)
        return Response({'results': data})

    @action(detail=False, methods=['get'])
    def market_overview(self, request):
        """市场概览：涨跌幅排行"""
        limit = int(request.query_params.get('limit', 20))
        data = StrategyService.market_overview(user=request.user, limit=limit)
        return Response({'results': data})

    @action(detail=False, methods=['get'])
    def correlation(self, request):
        """相关性分析矩阵"""
        symbols = request.query_params.get('symbols', 'BTC-USDT,ETH-USDT,SOL-USDT')
        bar = request.query_params.get('bar', '1D')
        limit = int(request.query_params.get('limit', 200))
        data = StrategyService.correlation_matrix(
            [s.strip() for s in symbols.split(',') if s.strip()],
            bar=bar, limit=limit, user=request.user,
        )
        return Response(data)

    @action(detail=False, methods=['get'])
    def factor_ic(self, request):
        """因子有效性统计（IC/IR）"""
        strategy_id = request.query_params.get('strategy_id')
        if not strategy_id:
            return Response({'error': 'strategy_id 必填'}, status=400)
        from apps.strategy.models import StrategyConfig
        strategy = StrategyConfig.objects.filter(id=strategy_id, user=request.user).first()
        if not strategy:
            return Response({'error': '策略不存在'}, status=404)
        data = StrategyService.factor_ic_analysis(
            strategy, bar=request.query_params.get('bar', '1D'),
            lookback=int(request.query_params.get('lookback', 100)), user=request.user,
        )
        return Response(data)

    @action(detail=False, methods=['get'])
    def market_state(self, request):
        """市场状态分类"""
        inst_id = request.query_params.get('inst_id', 'BTC-USDT')
        data = StrategyService.market_state(
            inst_id, bar=request.query_params.get('bar', '1D'),
            lookback=int(request.query_params.get('lookback', 60)), user=request.user,
        )
        return Response(data)

    @action(detail=False, methods=['get'])
    def net_value(self, request):
        """净值实时曲线（最近N天）"""
        days = int(request.query_params.get('days', 30))
        from apps.account.models import NetValueHistory
        since = timezone.now() - timedelta(days=days)
        rows = list(
            NetValueHistory.objects.filter(
                user=request.user, record_time__gte=since
            ).order_by('record_time')
        )
        data = [{
            'time': r.record_time.isoformat(),
            'net_value': float(r.total_eq),
            'daily_pnl': float(r.daily_pnl) if r.daily_pnl else None,
            'pnl_ratio': float(r.pnl_ratio) if r.pnl_ratio else None,
        } for r in rows]
        return Response({'results': data})
