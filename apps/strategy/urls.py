from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StrategyConfigViewSet, FactorDefinitionViewSet,
    SignalRecordViewSet, BacktestResultViewSet,
)

router = DefaultRouter()
router.register(r'configs', StrategyConfigViewSet, basename='strategy-config')
router.register(r'factors', FactorDefinitionViewSet, basename='factor-definition')
router.register(r'signals', SignalRecordViewSet, basename='signal-record')
router.register(r'backtests', BacktestResultViewSet, basename='backtest-result')

urlpatterns = [
    path('', include(router.urls)),
]
