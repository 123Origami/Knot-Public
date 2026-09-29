from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.bookings.models import Booking

class Review(models.Model):
    """
    User reviews after completed bookings.
    Both borrowers and stewards can leave reviews for each other.
    """
    
    REVIEW_TYPES = [
        ('borrower_to_steward', 'Borrower Review of Steward'),
        ('steward_to_borrower', 'Steward Review of Borrower'),
    ]
    
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    
    reviewer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='written_reviews'
    )
    reviewee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='received_reviews'
    )
    
    review_type = models.CharField(
        max_length=30,
        choices=REVIEW_TYPES
    )
    
    # Rating (1-5 stars)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Review content
    comment = models.TextField(
        max_length=1000
    )
    
    # Specific aspects (optional)
    communication_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    item_condition_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    timeliness_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True
    )
    
    # Response from reviewee
    response = models.TextField(
        max_length=1000,
        blank=True
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        ordering = ['-created_at']
        unique_together = ['booking', 'reviewer', 'review_type']
    
    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.reviewee.username} - {self.rating}★"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update reviewee's reputation
        self.reviewee.update_reputation()
    
    def add_response(self, text):
        """Add response to review"""
        self.response = text
        self.responded_at = timezone.now()
        self.save(update_fields=['response', 'responded_at'])