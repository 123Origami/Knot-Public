from rest_framework import serializers
from .models import Review

class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for reviews"""
    reviewer_name = serializers.CharField(source='reviewer.username', read_only=True)
    reviewee_name = serializers.CharField(source='reviewee.username', read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'booking', 'reviewer', 'reviewer_name', 'reviewee',
                  'reviewee_name', 'review_type', 'rating', 'comment',
                  'communication_rating', 'item_condition_rating',
                  'timeliness_rating', 'response', 'responded_at', 'created_at']
        read_only_fields = ['reviewer', 'response', 'responded_at', 'created_at']


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reviews"""
    
    class Meta:
        model = Review
        fields = ['booking', 'review_type', 'rating', 'comment',
                  'communication_rating', 'item_condition_rating', 'timeliness_rating']
    
    def validate(self, data):
        request_user = self.context['request'].user
        booking = data['booking']
        review_type = data['review_type']

        # Check that booking is completed
        if booking.status != 'completed':
            raise serializers.ValidationError("Can only review completed bookings")

        if request_user not in [booking.borrower, booking.item.steward]:
            raise serializers.ValidationError("You can only review bookings where you are borrower or steward")

        if review_type == 'borrower_to_steward' and request_user != booking.borrower:
            raise serializers.ValidationError("Only the borrower can submit this type of review")

        if review_type == 'steward_to_borrower' and request_user != booking.item.steward:
            raise serializers.ValidationError("Only the item steward can submit this type of review")

        if review_type == 'steward_to_borrower' and not data.get('timeliness_rating'):
            raise serializers.ValidationError("Timeliness rating is required when rating a borrower")
        
        # Check that user hasn't already reviewed this booking
        if Review.objects.filter(
            booking=booking,
            reviewer=request_user,
            review_type=review_type
        ).exists():
            raise serializers.ValidationError("You have already reviewed this booking")
        
        return data
    
    def create(self, validated_data):
        validated_data['reviewer'] = self.context['request'].user
        
        # Set reviewee based on review type
        booking = validated_data['booking']
        if validated_data['review_type'] == 'borrower_to_steward':
            validated_data['reviewee'] = booking.item.steward
        else:
            validated_data['reviewee'] = booking.borrower
        
        return super().create(validated_data)


class ReviewResponseSerializer(serializers.Serializer):
    """Serializer for responding to a review"""
    response = serializers.CharField(max_length=1000)