from django.conf import settings
from django.urls import path, include

urlpatterns = [
    # 不使用 Django 自带 /admin/，管理端由前端 Vue 实现
    path('api/market/', include('apps.market.urls')),
    path('api/account/', include('apps.account.urls')),
    path('api/strategy/', include('apps.strategy.urls')),
    path('api/orders/', include('apps.orders.urls')),
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
