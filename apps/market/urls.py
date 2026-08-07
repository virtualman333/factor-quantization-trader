from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InstrumentViewSet, KLineViewSet, TickerViewSet, FundingRateViewSet

router = DefaultRouter()
router.register(r'instruments', InstrumentViewSet, basename='instruments')
router.register(r'klines', KLineViewSet, basename='klines')
router.register(r'tickers', TickerViewSet, basename='tickers')
router.register(r'funding-rates', FundingRateViewSet, basename='funding-rates')

urlpatterns = [
    path('', include(router.urls)),
]
