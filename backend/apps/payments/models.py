from django.db import models
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.campaigns.models import Campaign, Organization
from apps.bookings.models import Booking
import uuid

class Transaction(models.Model):
    """
    Payment transactions via Payhero.
    Records all monetary transactions including contributions, fees, and refunds.
    """
    
    TRANSACTION_TYPES = [
        ('contribution', 'Campaign Contribution'),
        ('subscription', 'Membership Subscription'),
        ('booking_fee', 'Booking Fee'),
        ('deposit', 'Security Deposit'),
        ('refund', 'Refund'),
        ('payout', 'Organization Payout'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHODS = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Card (Visa/Mastercard)'),
        ('bank', 'Bank Transfer (PesaLink)'),
    ]
    
    # Transaction identifiers
    transaction_id = models.CharField(
        max_length=100, 
        unique=True
    )
    payhero_reference = models.CharField(
        max_length=100, 
        blank=True, 
        null=True
    )
    payhero_checkout_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True
    )
    
    # Transaction details
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPES
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHODS
    )
    
    # Amount and currency
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2
    )
    currency = models.CharField(
        max_length=3, 
        default='KES'
    )
    
    # M-Pesa specific
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True
    )
    mpesa_receipt = models.CharField(
        max_length=50, 
        blank=True, 
        null=True
    )
    
    # Related objects
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='transactions'
    )
    campaign = models.ForeignKey(
        Campaign, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    booking = models.ForeignKey(
        Booking, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='transactions'
    )
    
    # Metadata
    description = models.TextField(
        blank=True
    )
    metadata = models.JSONField(
        default=dict, 
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    completed_at = models.DateTimeField(
        blank=True, 
        null=True
    )
    
    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['payhero_reference']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['campaign', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.transaction_id:
            prefix = {
                'contribution': 'CON',
                'subscription': 'SUB',
                'booking_fee': 'BKF',
                'deposit': 'DEP',
                'refund': 'REF',
                'payout': 'PAY',
            }.get(self.transaction_type, 'TXN')
            
            unique_id = str(uuid.uuid4()).split('-')[0].upper()
            self.transaction_id = f"{prefix}-{unique_id}"
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.transaction_id} - {self.amount} KES"
    
    def mark_completed(self):
        """Mark transaction as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def mark_failed(self):
        """Mark transaction as failed"""
        self.status = 'failed'
        self.save(update_fields=['status'])
    
    def mark_refunded(self):
        """Mark transaction as refunded"""
        self.status = 'refunded'
        self.save(update_fields=['status'])


class Contribution(models.Model):
    """
    User contributions to campaigns.
    Links users to campaigns through successful transactions.
    """
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    transaction = models.OneToOneField(
        Transaction,
        on_delete=models.CASCADE,
        related_name='contribution'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    is_anonymous = models.BooleanField(
        default=False
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = "Contribution"
        verbose_name_plural = "Contributions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.amount} KES to {self.campaign.title}"


class Payout(models.Model):
    """
    Payouts to host organizations.
    When campaigns reach target, funds are paid out to organizations via Payhero.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    payout_id = models.CharField(
        max_length=100,
        unique=True
    )
    payhero_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.SET_NULL,
        null=True,
        related_name='payouts'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    currency = models.CharField(
        max_length=3,
        default='KES'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Bank details
    bank_name = models.CharField(
        max_length=100
    )
    account_name = models.CharField(
        max_length=200
    )
    account_number_encrypted = models.CharField(
        max_length=255
    )
    bank_code = models.CharField(
        max_length=10
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    processed_at = models.DateTimeField(
        blank=True,
        null=True
    )
    
    notes = models.TextField(
        blank=True
    )
    
    class Meta:
        verbose_name = "Payout"
        verbose_name_plural = "Payouts"
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.payout_id:
            unique_id = str(uuid.uuid4()).split('-')[0].upper()
            self.payout_id = f"PAYOUT-{unique_id}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Payout {self.payout_id} - {self.organization.name}"
    
    def mark_completed(self):
        """Mark payout as completed"""
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])