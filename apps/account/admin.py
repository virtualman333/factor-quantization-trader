"""Django Admin 后台注册"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    BalanceSnapshot, PositionSnapshot, NetValueHistory,
    OKXCredential, SystemConfig, UserQuota, GlobalConfig,
)


@admin.register(BalanceSnapshot)
class BalanceSnapshotAdmin(admin.ModelAdmin):
    list_display = ['user', 'ccy', 'total_eq', 'avail_eq', 'usd_value', 'snapshot_time']
    list_filter = ['ccy', 'snapshot_time']
    search_fields = ['user__username', 'ccy']


@admin.register(PositionSnapshot)
class PositionSnapshotAdmin(admin.ModelAdmin):
    list_display = ['user', 'inst_id', 'pos_side', 'pos', 'avg_px', 'mark_px', 'upl', 'leverage', 'snapshot_time']
    list_filter = ['inst_type', 'pos_side', 'snapshot_time']
    search_fields = ['user__username', 'inst_id']


@admin.register(NetValueHistory)
class NetValueHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_eq', 'total_pnl', 'daily_pnl', 'pnl_ratio', 'record_time']
    list_filter = ['record_time']
    search_fields = ['user__username']


@admin.register(OKXCredential)
class OKXCredentialAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'flag', 'is_active', 'updated_at']
    list_filter = ['name', 'is_active']
    search_fields = ['user__username']


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['user', 'active_environment', 'updated_at']
    list_filter = ['active_environment']
    search_fields = ['user__username']


@admin.register(UserQuota)
class UserQuotaAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'max_strategies', 'max_orders_per_day',
        'max_api_calls_per_minute', 'is_trading_enabled', 'updated_at',
    ]
    list_filter = ['is_trading_enabled']
    search_fields = ['user__username']


@admin.register(GlobalConfig)
class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'allow_registration', 'market_sync_interval',
        'market_sync_instruments', 'market_sync_tickers',
        'global_stop_loss_pct', 'global_default_leverage',
    ]
