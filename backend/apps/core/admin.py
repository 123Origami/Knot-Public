from django.contrib import admin
from .models import SiteSettings, Notification

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site', 'site_name', 'contact_email', 'maintenance_mode')
    fieldsets = (
        ('Site Info', {
            'fields': ('site', 'site_name', 'tagline')
        }),
        ('Contact', {
            'fields': ('contact_email', 'support_email')
        }),
        ('Features', {
            'fields': ('enable_payments', 'enable_messaging')
        }),
        ('Maintenance', {
            'fields': ('maintenance_mode', 'maintenance_message')
        }),
        ('Statistics', {
            'fields': ('total_users', 'total_items', 'total_campaigns', 'total_contributions'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('total_users', 'total_items', 'total_campaigns', 'total_contributions', 'updated_at')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)