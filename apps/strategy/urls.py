from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StrategyConfigViewSet, FactorDefinitionViewSet,
    SignalRecordViewSet, BacktestResultViewSet,
)

router = DefaultRouter()
router.register(r'configs', StrategyConfigViewSet)
router.register(r'factors', FactorDefinitionViewSet)
router.register(r'signals', SignalRecordViewSet)
router.register(r'backtests', BacktestResultViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
