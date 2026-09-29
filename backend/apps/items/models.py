from django.db import models
from django.utils.text import slugify
from apps.accounts.models import CustomUser

class Category(models.Model):
    """
    Item categories for organizing community resources.
    Categories help users browse and discover items.
    """
    
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Category name (e.g., 'Tools', 'Electronics')"
    )
    slug = models.SlugField(
        max_length=120, 
        unique=True,
        help_text="URL-friendly version of the name"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what belongs in this category"
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fa-tools')"
    )
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        help_text="Category image for display"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name


class Item(models.Model):
    """
    Community-owned items available for borrowing.
    Items are added by stewards after successful campaigns.
    """
    
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
    ]
    
    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text="Item name/title"
    )
    slug = models.SlugField(
        max_length=250,
        unique=True
    )
    description = models.TextField(
        help_text="Detailed description of the item"
    )
    
    # Categorization
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='items'
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags for search"
    )
    
    # Ownership & Stewardship
    steward = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name='managed_items'
    )
    host_organization = models.ForeignKey(
        'campaigns.Organization',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='items'
    )
    campaign = models.OneToOneField(
        'campaigns.Campaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acquired_item'
    )
    
    # Condition & Status
    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='good'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    
    # Location
    location_details = models.TextField(
        help_text="Where to pick up the item"
    )
    
    # Borrowing Rules
    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional rental fee per day (KES)"
    )
    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Security deposit amount (KES)"
    )
    max_borrow_days = models.IntegerField(
        default=14,
        help_text="Maximum days allowed per booking"
    )
    
    # Usage Tracking
    total_bookings = models.IntegerField(
        default=0,
        help_text="Total number of times borrowed"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        verbose_name = "Item"
        verbose_name_plural = "Items"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['category', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            counter = 1
            while Item.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    @property
    def primary_image(self):
        """Get the primary image for this item"""
        primary_img = self.images.filter(is_primary=True).first()
        return primary_img.image if primary_img else None

    @property
    def display_image_url(self):
        """Return a usable image URL with fallback for items without uploads."""
        primary_img = self.images.filter(is_primary=True).first() or self.images.first()
        if primary_img and primary_img.image:
            return primary_img.image.url
        return f"https://picsum.photos/seed/{self.slug}/600/400"
    
    def is_available(self, start_date=None, end_date=None):
        """Check if item is available for given date range"""
        if self.status in ['maintenance', 'retired']:
            return False
        
        if start_date and end_date:
            from apps.bookings.models import Booking
            conflicting = Booking.objects.filter(
                item=self,
                status__in=['pending', 'approved', 'paid', 'active', 'overdue'],
                start_date__lte=end_date,
                end_date__gte=start_date
            ).exists()
            return not conflicting
        
        return True


class ItemImage(models.Model):
    """
    Images for items (multiple per item).
    """
    
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(
        upload_to='item_images/'
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the main display image"
    )
    caption = models.CharField(
        max_length=200,
        blank=True
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = "Item Image"
        verbose_name_plural = "Item Images"
        ordering = ['-is_primary', 'uploaded_at']
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            ItemImage.objects.filter(item=self.item, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Image for {self.item.name}"


class ItemSuggestion(models.Model):
    """
    User suggestions for new items to acquire via campaigns.
    Community members can suggest items and vote on them.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('campaign_created', 'Campaign Created'),
    ]
    
    suggested_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='item_suggestions'
    )
    name = models.CharField(
        max_length=200
    )
    description = models.TextField(
        help_text="Why this item is needed and how it will be used"
    )
    estimated_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Estimated cost in KES"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='suggestions'
    )
    image = models.ImageField(
        upload_to='suggestion_images/',
        blank=True,
        null=True,
        help_text='Optional reference photo supplied by the member'
    )
    
    # Voting
    votes = models.IntegerField(
        default=0
    )
    voters = models.ManyToManyField(
        CustomUser,
        related_name='voted_suggestions',
        blank=True
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        verbose_name = "Item Suggestion"
        verbose_name_plural = "Item Suggestions"
        ordering = ['-votes', '-created_at']
    
    def __str__(self):
        return f"{self.name} (suggested by {self.suggested_by.username})"
    
    def add_vote(self, user):
        """Add a vote from a user"""
        if not self.voters.filter(id=user.id).exists():
            self.voters.add(user)
            self.votes = self.voters.count()
            self.save()
            return True
        return False
    
    def remove_vote(self, user):
        """Remove a vote from a user"""
        if self.voters.filter(id=user.id).exists():
            self.voters.remove(user)
            self.votes = self.voters.count()
            self.save()
            return True
        return False