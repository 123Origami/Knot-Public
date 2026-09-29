from rest_framework import serializers
from .models import SiteSettings, Notification

class SiteSettingsSerializer(serializers.ModelSerializer):
    """Serializer for site settings"""
    
    class Meta:
        model = SiteSettings
        fields = ['site_name', 'tagline', 'contact_email', 'support_email',
                  'enable_payments', 'enable_messaging', 'maintenance_mode',
                  'maintenance_message', 'total_users', 'total_items',
                  'total_campaigns', 'total_contributions']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for notifications"""
    
    class Meta:
        model = Notification
        fields = ['id', 'notification_type', 'title', 'message',
                  'related_url', 'is_read', 'created_at']
        read_only_fields = ['created_at']


class MarkReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    all = serializers.BooleanField(default=False)