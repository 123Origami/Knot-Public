from django.db import models
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.items.models import Item
import uuid

class Booking(models.Model):
    """
    Resource booking/rental records.
    Tracks when users borrow items, including dates, status, and check-in/out.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved - Payment Pending'),
        ('paid', 'Paid - Ready for Pickup'),
        ('declined', 'Declined'),
        ('active', 'Active (Checked Out)'),
        ('completed', 'Completed (Returned)'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue'),
    ]
    
    booking_id = models.CharField(
        max_length=50,
        unique=True
    )
    
    # Related objects
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='bookings'
    )
    borrower = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='bookings_as_borrower'
    )
    steward = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_bookings'
    )
    
    # Booking dates
    start_date = models.DateField(
        help_text="Start date of the booking period"
    )
    end_date = models.DateField(
        help_text="End date of the booking period"
    )
    
    # Pickup details (set by admin after approval)
    pickup_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when item can be picked up"
    )
    pickup_location = models.TextField(
        blank=True,
        help_text="Location where item can be picked up"
    )
    pickup_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Time when item can be picked up"
    )
    
    # Purpose
    purpose = models.TextField(
        blank=True
    )

    borrower_id_photo = models.ImageField(
        upload_to='booking_request_ids/',
        blank=True,
        null=True,
        help_text='Borrower ID photo submitted with booking request'
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Check-in/out tracking
    checked_out_at = models.DateTimeField(
        null=True,
        blank=True
    )
    returned_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Financial (if applicable)
    total_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    deposit_paid = models.BooleanField(
        default=False
    )
    deposit_refunded = models.BooleanField(
        default=False
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Payment Pending'),
            ('paid', 'Paid'),
            ('refunded', 'Refunded'),
            ('failed', 'Payment Failed'),
        ],
        default='pending',
        help_text="Payment status for the booking"
    )
    payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When payment was completed"
    )
    
    # Notes
    notes = models.TextField(
        blank=True
    )
    borrower_notes = models.TextField(
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking_id']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['borrower', 'status']),
            models.Index(fields=['item', 'start_date', 'end_date']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.booking_id:
            year = timezone.now().year
            last_booking = Booking.objects.filter(
                booking_id__startswith=f'BKG-{year}'
            ).order_by('-booking_id').first()
            
            if last_booking:
                last_num = int(last_booking.booking_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.booking_id = f'BKG-{year}-{new_num:04d}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.booking_id} - {self.item.name}"
    
    def duration_days(self):
        """Calculate duration in days"""
        return (self.end_date - self.start_date).days
    
    def is_active(self):
        """Check if booking is currently active"""
        return self.status == 'active'
    
    def is_overdue(self):
        """Check if booking is overdue"""
        if self.status == 'active' and timezone.now().date() > self.end_date:
            return True
        return False
    
    def check_in(self):
        """Mark item as checked in (returned)"""
        self.status = 'completed'
        self.returned_at = timezone.now()
        self.save()
        
        # Update item status
        self.item.status = 'available'
        self.item.save()
    
    def check_out(self):
        """Mark item as checked out"""
        self.status = 'active'
        self.checked_out_at = timezone.now()
        self.save()
        
        # Update item status
        self.item.status = 'borrowed'
        self.item.save()
    
    def cancel(self):
        """Cancel booking"""
        self.status = 'cancelled'
        self.save()


class BookingHistory(models.Model):
    """
    Audit log for booking status changes.
    Tracks all actions performed on a booking for accountability.
    """
    
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('checked_out', 'Checked Out'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue'),
    ]
    
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='history'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )
    performed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True
    )
    timestamp = models.DateTimeField(
        auto_now_add=True
    )
    notes = models.TextField(
        blank=True
    )
    
    class Meta:
        verbose_name = "Booking History"
        verbose_name_plural = "Booking Histories"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.booking.booking_id} - {self.action}"