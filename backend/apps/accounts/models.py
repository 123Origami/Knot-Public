from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta

class CustomUser(AbstractUser):
    """
    Extended user model for Knot platform.
    
    This model extends Django's built-in AbstractUser to add fields specific to the
    community sharing platform including verification levels, reputation metrics,
    and profile information.
    """
    
    # Admin request fields 
    REQUEST_STATUS = [
        ('none', 'No Request'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    admin_request_status = models.CharField(
        max_length=20,
        choices=REQUEST_STATUS,
        default='none',
        help_text="Status of admin request"
    )
    admin_request_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for requesting admin access"
    )
    admin_request_id_photo = models.ImageField(
        upload_to='admin_request_ids/',
        blank=True,
        null=True,
        help_text='Photo of government-issued ID submitted for admin request review'
    )
    admin_request_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When admin was requested"
    )
    admin_request_reviewed_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_admin_requests',
        help_text="Which admin reviewed this request"
    )
    admin_request_review_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was reviewed"
    )
    admin_request_review_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes from admin review"
    )
    
    # Helper properties
    @property
    def is_admin_approved(self):
        return self.admin_request_status == 'approved'
    
    @property
    def has_pending_admin_request(self):
        return self.admin_request_status == 'pending'

    VERIFICATION_LEVELS = [
        (0, 'Unverified'),
        (1, 'Email Verified'),
        (2, 'Phone Verified'),
        (3, 'ID Verified'),
    ]
    
    # Contact Information
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        help_text="Kenyan phone number format (e.g., 0712345678 or 254712345678)"
    )
    
    # Verification Status
    verification_level = models.IntegerField(
        choices=VERIFICATION_LEVELS, 
        default=0,
        help_text="Current verification tier of the user"
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="Whether email has been verified"
    )
  
    phone_verified = models.BooleanField(
        default=False,
        help_text="Whether phone number has been verified"
    )
    id_verified = models.BooleanField(
        default=False,
        help_text="Whether government ID has been verified"
    )
    
    # Profile Information
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True,
        help_text="User profile picture (optional)"
    )
    bio = models.TextField(
        max_length=500,
        blank=True,
        help_text="Short biography about the user"
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Neighborhood or general location"
    )
    
    # Reputation Metrics
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        help_text="Average rating from reviews (0.00 to 5.00)"
    )
    total_reviews = models.IntegerField(
        default=0,
        help_text="Total number of reviews received"
    )
    successful_bookings = models.IntegerField(
        default=0,
        help_text="Number of successfully completed bookings as borrower"
    )
    successful_lendings = models.IntegerField(
        default=0,
        help_text="Number of successfully completed bookings as lender/steward"
    )
    cancelled_bookings = models.IntegerField(
        default=0,
        help_text="Number of bookings cancelled by user"
    )
    
    # Timestamps
    date_joined = models.DateTimeField(
        auto_now_add=True,
        help_text="When user registered"
    )
    last_active = models.DateTimeField(
        default=timezone.now,
        help_text="Last time user was active on platform"
    )
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
            models.Index(fields=['verification_level']),
            models.Index(fields=['-average_rating']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def get_verification_badge(self):
        """Return visual badge for verification level"""
        badges = {
            0: '🔴 Unverified',
            1: '🟡 Email Verified',
            2: '🟢 Phone Verified',
            3: '⭐ Fully Verified'
        }
        return badges.get(self.verification_level, 'Unknown')
    
    def update_reputation(self):
        """Calculate and update average rating from all reviews"""
        from apps.reviews.models import Review
        reviews = Review.objects.filter(reviewee=self)
        if reviews.exists():
            avg = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.average_rating = round(avg, 2)
            self.total_reviews = reviews.count()
            self.save(update_fields=['average_rating', 'total_reviews'])


class EmailVerificationToken(models.Model):
    """
    Token for email verification.
    Generated when a user registers. Expires after 30 minutes.
    """
    user = models.OneToOneField(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='email_verification_token'
    )
    token = models.CharField(
        max_length=100, 
        unique=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    expires_at = models.DateTimeField()
    
    class Meta:
        verbose_name = "Email Verification Token"
        verbose_name_plural = "Email Verification Tokens"
    
    def save(self, *args, **kwargs):
        """Set expiry to 30 minutes from creation if not set"""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=30)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Check if token is still valid (not expired)"""
        return timezone.now() <= self.expires_at
    
    def __str__(self):
        return f"Token for {self.user.email} (expires {self.expires_at})"


class PasswordResetToken(models.Model):
    """
    Token for password reset.
    Generated when user requests password reset. Expires after 1 hour.
    """
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token = models.CharField(
        max_length=100, 
        unique=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    expires_at = models.DateTimeField()
    used = models.BooleanField(
        default=False
    )
    
    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"
    
    def save(self, *args, **kwargs):
        """Set expiry to 1 hour from creation if not set"""
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)
    
    def is_valid(self):
        """Check if token is valid (not expired and not used)"""
        return not self.used and timezone.now() <= self.expires_at
    
    def __str__(self):
        return f"Password reset for {self.user.email}"