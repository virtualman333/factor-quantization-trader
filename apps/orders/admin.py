from django.contrib import admin
from .models import TradeOrder, OrderLog


class OrderLogInline(admin.TabularInline):
    model = OrderLog
    extra = 0
    readonly_fields = ['action', 'detail', 'created_at']
    can_delete = False


@admin.register(TradeOrder)
class TradeOrderAdmin(admin.ModelAdmin):
    list_display = ['ord_id', 'inst_id', 'side', 'ord_type', 'sz', 'px',
                    'fill_sz', 'fill_px', 'state', 'source', 'created_at']
    list_filter = ['state', 'side', 'ord_type', 'inst_id', 'source']
    search_fields = ['ord_id', 'cl_ord_id', 'inst_id']
    readonly_fields = ['ord_id', 'fill_sz', 'fill_px', 'fee', 'state']
    inlines = [OrderLogInline]
    date_hierarchy = 'created_at'


@admin.register(OrderLog)
class OrderLogAdmin(admin.ModelAdmin):
    list_display = ['order', 'action', 'created_at']
    list_filter = ['action']
    readonly_fields = ['order', 'action', 'detail', 'created_at']
