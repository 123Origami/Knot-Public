from rest_framework import serializers
from django.utils import timezone
from .models import Booking, BookingHistory
from .services import get_unreturned_overdue_bookings_for_borrower

class BookingSerializer(serializers.ModelSerializer):
    """Serializer for bookings"""
    item_name = serializers.CharField(source='item.name', read_only=True)
    item_image = serializers.ImageField(source='item.images.filter(is_primary=True).first.image', read_only=True)
    borrower_name = serializers.CharField(source='borrower.username', read_only=True)
    steward_name = serializers.CharField(source='steward.username', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = ['id', 'booking_id', 'item', 'item_name', 'item_image',
                  'borrower', 'borrower_name', 'steward', 'steward_name',
                  'start_date', 'end_date', 'pickup_time', 'return_time',
                  'purpose', 'borrower_id_photo', 'status', 'duration', 'created_at']
        read_only_fields = ['booking_id', 'status', 'created_at']
    
    def get_duration(self, obj):
        return obj.duration_days()


class BookingDetailSerializer(BookingSerializer):
    """Detailed serializer for single booking view"""
    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ['notes', 'borrower_notes',
                  'checked_out_at', 'returned_at', 'total_fee',
                  'deposit_paid', 'deposit_refunded', 'pickup_date',
                  'pickup_location', 'pickup_time', 'payment_status',
                  'payment_date', 'updated_at']


class BookingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating bookings"""
    
    class Meta:
        model = Booking
        fields = ['item', 'start_date', 'end_date', 'pickup_time', 'return_time', 'purpose', 'borrower_id_photo']
    
    def validate(self, data):
        request = self.context.get('request')
        borrower = getattr(request, 'user', None)
        overdue_qs = get_unreturned_overdue_bookings_for_borrower(borrower)
        if overdue_qs.exists():
            raise serializers.ValidationError(
                'You have overdue items that have not been returned. Return them before booking another item.'
            )

        today = timezone.localdate()
        if data['start_date'] < today or data['end_date'] < today:
            raise serializers.ValidationError('Past dates cannot be booked.')

        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after start date")
        
        # Check availability
        item = data['item']
        if not item.is_available(data['start_date'], data['end_date']):
            raise serializers.ValidationError("Item is not available for selected dates")
        
        # Check max borrow days
        duration = (data['end_date'] - data['start_date']).days + 1
        if duration > item.max_borrow_days:
            raise serializers.ValidationError(
                f"Cannot borrow for more than {item.max_borrow_days} days"
            )

        id_photo = data.get('borrower_id_photo')
        if not id_photo:
            raise serializers.ValidationError('Please upload an ID photo to submit this booking request.')
        
        return data


class BookingActionSerializer(serializers.Serializer):
    """Serializer for booking actions (approve/decline/cancel)"""
    notes = serializers.CharField(required=False, allow_blank=True)
    pickup_date = serializers.DateField(required=False)
    pickup_location = serializers.CharField(required=False, allow_blank=True)
    pickup_time = serializers.TimeField(required=False)


class BookingHistorySerializer(serializers.ModelSerializer):
    """Serializer for booking history"""
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = BookingHistory
        fields = ['action', 'performed_by', 'performed_by_name', 'timestamp', 'notes']