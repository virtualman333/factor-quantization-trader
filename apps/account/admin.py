from django.contrib import admin
from .models import BalanceSnapshot, PositionSnapshot, NetValueHistory


@admin.register(BalanceSnapshot)
class BalanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ['ccy', 'total_eq', 'avail_eq', 'usd_value', 'snapshot_time']
    list_filter = ['ccy']
    date_hierarchy = 'snapshot_time'


@admin.register(PositionSnapshot)
class PositionSnapshotAdmin(admin.ModelAdmin):
    list_display = ['inst_id', 'pos_side', 'pos', 'avg_px', 'mark_px', 'upl', 'leverage', 'snapshot_time']
    list_filter = ['inst_id', 'pos_side']
    date_hierarchy = 'snapshot_time'


@admin.register(NetValueHistory)
class NetValueHistoryAdmin(admin.ModelAdmin):
    list_display = ['total_eq', 'total_pnl', 'daily_pnl', 'pnl_ratio', 'record_time']
    date_hierarchy = 'record_time'
