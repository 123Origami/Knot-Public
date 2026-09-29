from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.sites.models import Site
from .models import SiteSettings, Notification
from .serializers import SiteSettingsSerializer, NotificationSerializer, MarkReadSerializer

class SiteSettingsView(generics.RetrieveAPIView):
    """Get site settings"""
    permission_classes = [permissions.AllowAny]
    serializer_class = SiteSettingsSerializer
    
    def get_object(self):
        site = Site.objects.get_current()
        settings, created = SiteSettings.objects.get_or_create(site=site)
        return settings


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for user notifications"""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def mark_read(self, request):
        """Mark notifications as read"""
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        if data.get('all'):
            # Mark all as read
            notifications = self.get_queryset().filter(is_read=False)
            for notification in notifications:
                notification.mark_as_read()
            return Response({'status': f'{notifications.count()} notifications marked as read'})
        
        elif data.get('notification_ids'):
            # Mark specific notifications as read
            notifications = self.get_queryset().filter(
                id__in=data['notification_ids'],
                is_read=False
            )
            for notification in notifications:
                notification.mark_as_read()
            return Response({'status': f'{notifications.count()} notifications marked as read'})
        
        return Response({'status': 'no notifications marked'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})