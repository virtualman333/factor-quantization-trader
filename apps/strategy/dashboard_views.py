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
