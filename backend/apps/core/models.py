from django.db import models
from django.contrib.sites.models import Site
from django.utils import timezone
from apps.accounts.models import CustomUser

class SiteSettings(models.Model):
    """
    Global site settings.
    Stores configuration and cached statistics.
    """
    
    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    
    # Site information
    site_name = models.CharField(
        max_length=100,
        default='Knot'
    )
    tagline = models.CharField(
        max_length=200,
        default='Tying Communities Together Through Shared Resources'
    )
    
    # Contact information
    contact_email = models.EmailField(
        blank=True
    )
    support_email = models.EmailField(
        blank=True
    )
    
    # Feature flags
    enable_payments = models.BooleanField(
        default=False
    )
    enable_messaging = models.BooleanField(
        default=True
    )
    
    # Maintenance mode
    maintenance_mode = models.BooleanField(
        default=False
    )
    maintenance_message = models.TextField(
        blank=True
    )
    
    # Cached statistics
    total_users = models.IntegerField(
        default=0
    )
    total_items = models.IntegerField(
        default=0
    )
    total_campaigns = models.IntegerField(
        default=0
    )
    total_contributions = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Timestamps
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"
    
    def __str__(self):
        return f"Settings for {self.site.name}"

    @classmethod
    def payments_enabled(cls):
        """Whether live payments (M-Pesa/PayHero) are turned on site-wide."""
        site = Site.objects.get_current()
        settings_obj, _ = cls.objects.get_or_create(site=site)
        return settings_obj.enable_payments
    
    def update_statistics(self):
        """Update cached statistics"""
        from apps.accounts.models import CustomUser
        from apps.items.models import Item
        from apps.campaigns.models import Campaign
        from apps.payments.models import Contribution
        
        self.total_users = CustomUser.objects.count()
        self.total_items = Item.objects.filter(status__in=['available', 'borrowed']).count()
        self.total_campaigns = Campaign.objects.filter(status='active').count()
        
        total = Contribution.objects.aggregate(total=models.Sum('amount'))['total']
        self.total_contributions = total or 0
        
        self.save(update_fields=['total_users', 'total_items', 'total_campaigns', 'total_contributions'])


class Notification(models.Model):
    """
    User notifications.
    In-app notifications for various events.
    """
    
    NOTIFICATION_TYPES = [
        ('booking_request', 'Booking Request'),
        ('booking_approved', 'Booking Approved'),
        ('booking_declined', 'Booking Declined'),
        ('booking_reminder', 'Booking Reminder'),
        ('booking_overdue', 'Booking Overdue'),
        ('campaign_funded', 'Campaign Funded'),
        ('campaign_expiring', 'Campaign Expiring'),
        ('new_message', 'New Message'),
        ('new_review', 'New Review'),
        ('payment_received', 'Payment Received'),
        ('payout_completed', 'Payout Completed'),
        ('system', 'System Notification'),
    ]
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPES
    )
    
    title = models.CharField(
        max_length=200
    )
    message = models.TextField()
    
    # Link to related object
    related_url = models.CharField(
        max_length=500,
        blank=True
    )
    
    # Read status
    is_read = models.BooleanField(
        default=False
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Email status
    email_sent = models.BooleanField(
        default=False
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])