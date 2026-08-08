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
