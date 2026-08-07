from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BalanceSnapshotViewSet, PositionSnapshotViewSet, NetValueHistoryViewSet,
    OKXCredentialViewSet, SystemConfigViewSet,
)
from .auth_views import LoginView, RegisterView, TokenRefreshView, MeView

router = DefaultRouter()
router.register(r'balances', BalanceSnapshotViewSet)
router.register(r'positions', PositionSnapshotViewSet)
router.register(r'net-value', NetValueHistoryViewSet)
router.register(r'credentials', OKXCredentialViewSet, basename='credentials')
router.register(r'system-config', SystemConfigViewSet, basename='system-config')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('', include(router.urls)),
]


