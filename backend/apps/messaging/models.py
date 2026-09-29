from django.db import models
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.items.models import Item
from apps.bookings.models import Booking

class Conversation(models.Model):
    """
    Message threads between users.
    Each conversation has two or more participants and relates to an item or booking.
    """
    
    participants = models.ManyToManyField(
        CustomUser,
        related_name='conversations'
    )
    
    # Related objects (optional)
    related_item = models.ForeignKey(
        Item,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    related_booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    
    subject = models.CharField(
        max_length=200,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    is_active = models.BooleanField(
        default=True
    )
    
    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ['-updated_at']
    
    def __str__(self):
        participants_str = ", ".join([p.username for p in self.participants.all()[:3]])
        if self.participants.count() > 3:
            participants_str += f" and {self.participants.count() - 3} others"
        return f"Conversation: {participants_str}"
    
    def get_other_participant(self, user):
        """Get the other participant in a 2-person conversation"""
        return self.participants.exclude(id=user.id).first()
    
    def last_message(self):
        """Get the most recent message"""
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    """
    Individual messages within conversations.
    """
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    
    content = models.TextField()
    
    # Read status
    is_read = models.BooleanField(
        default=False
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at}"
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])