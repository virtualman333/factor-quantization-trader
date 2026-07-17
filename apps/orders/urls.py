from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TradeOrderViewSet, OrderLogViewSet

router = DefaultRouter()
router.register(r'trades', TradeOrderViewSet)
router.register(r'logs', OrderLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
