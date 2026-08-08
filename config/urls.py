from django.conf import settings
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # 不使用 Django 自带 /admin/，管理端由前端 Vue 实现
    # 直接访问后端 /admin 时重定向到前端管理端页面
    path(
        'admin/',
        RedirectView.as_view(url=f"{settings.FRONTEND_URL}/admin", permanent=False),
        name='admin-redirect',
    ),
    path('api/market/', include('apps.market.urls')),
    path('api/account/', include('apps.account.urls')),
    path('api/strategy/', include('apps.strategy.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
]

# ---- 性能监控路由（仅开发环境） ----
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        # Silk 请求性能分析界面: /silk/
        path('silk/', include('silk.urls', namespace='silk')),
        # Django Debug Toolbar: 由中间件注入，无需路由（仍需注册以兼容）
        path('__debug__/', include(debug_toolbar.urls)),
    ]

# ---- OpenAPI 3.0 + Swagger UI (drf-spectacular, 可选) ----
try:
    from drf_spectacular.views import (
        SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
    )
    from rest_framework.permissions import AllowAny, IsAuthenticated
    # DEBUG 模式下允许匿名访问 Swagger UI，方便前端/第三方对接；生产默认 DRF 全局权限 (IsAuthenticated)
    perm = [AllowAny] if settings.DEBUG else [IsAuthenticated]
    urlpatterns += [
        # 原始 YAML / JSON schema 下载
        path('api/schema/',
             SpectacularAPIView.as_view(permission_classes=perm),
             name='schema'),
        # Swagger UI: 访问 /api/docs/ 即可在线调试
        path('api/docs/',
             SpectacularSwaggerView.as_view(url_name='schema', permission_classes=perm),
             name='swagger-ui'),
        # ReDoc UI: 文档阅读页
        path('api/redoc/',
             SpectacularRedocView.as_view(url_name='schema', permission_classes=perm),
             name='redoc'),
    ]
except ImportError:  # 未安装 drf-spectacular 则跳过
    pass
