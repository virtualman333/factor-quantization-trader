from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StrategyConfigViewSet, FactorDefinitionViewSet,
    SignalRecordViewSet, BacktestResultViewSet, PortfolioViewSet,
)
from .dashboard_views import DashboardViewSet

router = DefaultRouter()
router.register(r'configs', StrategyConfigViewSet, basename='strategy-config')
router.register(r'factors', FactorDefinitionViewSet, basename='factor-definition')
router.register(r'signals', SignalRecordViewSet, basename='signal-record')
router.register(r'backtests', BacktestResultViewSet, basename='backtest-result')
router.register(r'portfolios', PortfolioViewSet, basename='strategy-portfolio')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
