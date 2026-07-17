from django.contrib import admin
from .models import Instrument, KLine, Ticker, FundingRate


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ['inst_id', 'inst_type', 'base_ccy', 'quote_ccy', 'state', 'is_active']
    list_filter = ['inst_type', 'state', 'is_active']
    search_fields = ['inst_id', 'base_ccy', 'quote_ccy']


@admin.register(KLine)
class KLineAdmin(admin.ModelAdmin):
    list_display = ['instrument', 'bar', 'timestamp', 'open', 'high', 'low', 'close', 'vol', 'confirm']
    list_filter = ['bar', 'confirm']
    search_fields = ['instrument__inst_id']
    date_hierarchy = 'timestamp'


@admin.register(Ticker)
class TickerAdmin(admin.ModelAdmin):
    list_display = ['instrument', 'last', 'open_24h', 'high_24h', 'low_24h', 'vol_24h']
    search_fields = ['instrument__inst_id']


@admin.register(FundingRate)
class FundingRateAdmin(admin.ModelAdmin):
    list_display = ['instrument', 'funding_rate', 'funding_time', 'realized_rate']
    list_filter = ['instrument']
    date_hierarchy = 'funding_time'
