from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/market/', include('apps.market.urls')),
    path('api/account/', include('apps.account.urls')),
    path('api/strategy/', include('apps.strategy.urls')),
    path('api/orders/', include('apps.orders.urls')),
]
