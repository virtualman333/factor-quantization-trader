from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'type', 'level', 'title', 'user', 'read', 'created_at']
    list_filter = ['type', 'level', 'read', 'created_at']
    search_fields = ['title', 'content']
    date_hierarchy = 'created_at'
