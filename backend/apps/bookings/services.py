from django.db.models import Q
from django.utils import timezone

from apps.core.models import Notification

from .models import Booking, BookingHistory


def sync_overdue_bookings_for_user(user=None):
    """Mark overdue active bookings and notify borrowers once per booking."""
    today = timezone.now().date()
    overdue_qs = Booking.objects.filter(status='active', end_date__lt=today)

    if user is not None:
        overdue_qs = overdue_qs.filter(Q(borrower=user) | Q(item__steward=user))

    overdue_bookings = overdue_qs.select_related('borrower', 'item', 'item__steward')
    updated_count = 0

    for booking in overdue_bookings:
        booking.status = 'overdue'
        booking.save(update_fields=['status', 'updated_at'])
        updated_count += 1

        BookingHistory.objects.create(
            booking=booking,
            action='overdue',
            performed_by=booking.item.steward,
            notes='Booking automatically marked as overdue after return date passed.',
        )

        related_url = f'/dashboard/?booking={booking.booking_id}'
        already_notified = Notification.objects.filter(
            user=booking.borrower,
            notification_type='booking_overdue',
            related_url=related_url,
        ).exists()

        if not already_notified:
            Notification.objects.create(
                user=booking.borrower,
                notification_type='booking_overdue',
                title='Booking Is Overdue',
                message=(
                    f'Your booking for {booking.item.name} is overdue. '
                    'Please return the item as soon as possible.'
                ),
                related_url=related_url,
            )

    return updated_count


def get_unreturned_overdue_bookings_for_borrower(user):
    """Return overdue bookings that block a borrower from creating new bookings."""
    if not user or not getattr(user, 'is_authenticated', False):
        return Booking.objects.none()

    today = timezone.now().date()
    return Booking.objects.filter(
        borrower=user,
    ).filter(
        Q(status='overdue') | Q(status='active', end_date__lt=today)
    )
