from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TradeOrderViewSet, OrderLogViewSet, OrderTemplateViewSet

router = DefaultRouter()
router.register(r'trades', TradeOrderViewSet, basename='trade-order')
router.register(r'logs', OrderLogViewSet, basename='order-log')
router.register(r'templates', OrderTemplateViewSet, basename='order-template')

urlpatterns = [
    path('', include(router.urls)),
]
