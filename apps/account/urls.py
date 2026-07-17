from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BalanceSnapshotViewSet, PositionSnapshotViewSet, NetValueHistoryViewSet,
    OKXCredentialViewSet, SystemConfigViewSet,
)

router = DefaultRouter()
router.register(r'balances', BalanceSnapshotViewSet)
router.register(r'positions', PositionSnapshotViewSet)
router.register(r'net-value', NetValueHistoryViewSet)
router.register(r'credentials', OKXCredentialViewSet, basename='credentials')
router.register(r'system-config', SystemConfigViewSet, basename='system-config')

urlpatterns = [
    path('', include(router.urls)),
]


