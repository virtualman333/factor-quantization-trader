from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InstrumentViewSet, KLineViewSet, TickerViewSet, FundingRateViewSet

router = DefaultRouter()
router.register(r'instruments', InstrumentViewSet)
router.register(r'klines', KLineViewSet)
router.register(r'tickers', TickerViewSet)
router.register(r'funding-rates', FundingRateViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
