from django.contrib import admin
from .models import StrategyConfig, FactorDefinition, SignalRecord, BacktestResult


@admin.register(StrategyConfig)
class StrategyConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'inst_type', 'direction', 'status', 'bar',
                    'order_size_pct', 'max_positions', 'updated_at']
    list_filter = ['status', 'inst_type', 'direction']
    search_fields = ['name', 'symbols']

    def get_queryset(self, request):
        # 所有用户（含管理员）仅可见自己的策略
        return super().get_queryset(request).filter(user=request.user)


@admin.register(FactorDefinition)
class FactorDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'factor_type', 'is_active']
    list_filter = ['factor_type', 'is_active']
    search_fields = ['name', 'display_name']


@admin.register(SignalRecord)
class SignalRecordAdmin(admin.ModelAdmin):
    list_display = ['strategy', 'inst_id', 'signal', 'score', 'price',
                    'is_executed', 'created_at']
    list_filter = ['signal', 'is_executed', 'strategy']
    search_fields = ['inst_id']
    date_hierarchy = 'created_at'


@admin.register(BacktestResult)
class BacktestResultAdmin(admin.ModelAdmin):
    list_display = ['strategy', 'start_date', 'end_date', 'total_return',
                    'sharpe_ratio', 'max_drawdown', 'win_rate', 'total_trades']
    list_filter = ['strategy']

    def get_queryset(self, request):
        # 所有用户（含管理员）仅可见自己的回测结果
        return super().get_queryset(request).filter(strategy__user=request.user)
