from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from apps.accounts.models import CustomUser
from apps.items.models import Category, ItemSuggestion

class Organization(models.Model):
    """
    Host organizations (NGOs, community centers, libraries) that steward resources.
    These organizations provide physical space and staff to manage community assets.
    """
    
    name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Organization name"
    )
    slug = models.SlugField(
        max_length=250,
        unique=True
    )
    description = models.TextField(
        help_text="Description of the organization and its mission"
    )
    logo = models.ImageField(
        upload_to='organization_logos/',
        blank=True,
        null=True
    )
    
    # Contact Information
    address = models.TextField(
        help_text="Physical address"
    )
    contact_email = models.EmailField()
    contact_phone = models.CharField(
        max_length=15
    )
    website = models.URLField(
        blank=True
    )
    
    # Location for map display
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Payment Details (for payouts)
    payhero_merchant_id = models.CharField(
        max_length=100,
        blank=True
    )
    bank_name = models.CharField(
        max_length=100,
        blank=True
    )
    account_name = models.CharField(
        max_length=200,
        blank=True
    )
    account_number_encrypted = models.CharField(
        max_length=255,
        blank=True
    )
    bank_code = models.CharField(
        max_length=10,
        blank=True
    )
    
    # Staff
    stewards = models.ManyToManyField(
        CustomUser,
        related_name='managed_organizations'
    )
    
    # Status
    is_verified = models.BooleanField(
        default=False
    )
    is_active = models.BooleanField(
        default=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        verbose_name = "Organization"
        verbose_name_plural = "Organizations"
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Campaign(models.Model):
    """
    Crowdfunding campaigns to acquire new community resources.
    Campaigns are created by community members and hosted by organizations.
    Funds are collected via Payhero and paid out to organizations upon success.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('funded', 'Funded'),
        ('completed', 'Completed (Item Acquired)'),
        ('expired', 'Expired (Not Funded)'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic Information
    title = models.CharField(
        max_length=200
    )
    slug = models.SlugField(
        max_length=250,
        unique=True
    )
    description = models.TextField()
    image = models.ImageField(
        upload_to='campaign_images/',
        blank=True,
        null=True
    )
    
    # Financial Targets
    target_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    funds_raised = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    min_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1.00
    )
    
    # Related Items
    suggested_item = models.ForeignKey(
        ItemSuggestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='campaigns'
    )
    
    # Stakeholders
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='created_campaigns'
    )
    host_organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='campaigns'
    )
    
    # Dates
    start_date = models.DateTimeField(
        default=timezone.now
    )
    end_date = models.DateTimeField()
    funded_date = models.DateTimeField(
        null=True,
        blank=True
    )
    funds_pulled_out = models.BooleanField(
        default=False,
        help_text="Whether admin has completed pullout after funding goal is reached"
    )
    pulled_out_at = models.DateTimeField(
        null=True,
        blank=True
    )
    pulled_out_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_pullouts'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Statistics
    contributor_count = models.IntegerField(
        default=0
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['end_date']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            unique_slug = base_slug
            counter = 1
            while Campaign.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

        # Keep funding state consistent regardless of where funds are updated
        # (callbacks, admin edits, scripts, or API paths).
        if self.status == 'active' and self.funds_raised >= self.target_amount:
            now = timezone.now()
            Campaign.objects.filter(id=self.id, status='active').update(
                status='funded',
                funded_date=now,
                updated_at=now,
            )
            self.status = 'funded'
            self.funded_date = now
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def get_progress_percentage(self):
        """Calculate campaign progress percentage"""
        if self.target_amount > 0:
            return min(round((self.funds_raised / self.target_amount) * 100), 100)
        return 0
    
    def days_remaining(self):
        """Calculate days remaining until campaign ends"""
        if self.status != 'active':
            return 0
        remaining = (self.end_date - timezone.now()).days
        return max(remaining, 0)
    
    def check_if_funded(self):
        """Check if campaign has reached target and update status"""
        if self.status == 'active' and self.funds_raised >= self.target_amount:
            self.status = 'funded'
            self.funded_date = timezone.now()
            self.save(update_fields=['status', 'funded_date'])
            return True
        return False
    
    def check_if_expired(self):
        """Check if campaign has expired and update status"""
        if self.status == 'active' and timezone.now() > self.end_date:
            self.status = 'expired'
            self.save(update_fields=['status'])
            return True
        return False