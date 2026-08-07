from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BalanceSnapshotViewSet, PositionSnapshotViewSet, NetValueHistoryViewSet,
    OKXCredentialViewSet, SystemConfigViewSet,
)
from .admin_views import (
    AdminUserViewSet, UserQuotaViewSet, GlobalConfigViewSet, AdminConfigView,
)
from .auth_views import (
    LoginView, RegisterView, TokenRefreshView, MeView, ChangePasswordView,
)

router = DefaultRouter()
router.register(r'balances', BalanceSnapshotViewSet, basename='balances')
router.register(r'positions', PositionSnapshotViewSet, basename='positions')
router.register(r'net-value', NetValueHistoryViewSet, basename='netvalue')
router.register(r'credentials', OKXCredentialViewSet, basename='credentials')
router.register(r'system-config', SystemConfigViewSet, basename='system-config')
router.register(r'admin/users', AdminUserViewSet, basename='admin-users')
router.register(r'admin/quotas', UserQuotaViewSet, basename='admin-quotas')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('admin/global-config/', GlobalConfigViewSet.as_view({'get': 'list', 'post': 'create'}), name='admin-global-config'),
    path('admin/overview/', AdminConfigView.as_view(), name='admin-overview'),
    path('', include(router.urls)),
]
