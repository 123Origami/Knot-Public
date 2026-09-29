from rest_framework import serializers
from .models import Transaction, Contribution, Payout

class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for transactions"""
    
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_id', 'transaction_type', 'status',
                  'payment_method', 'amount', 'currency', 'description',
                  'created_at', 'completed_at']
        read_only_fields = ['transaction_id', 'status', 'created_at', 'completed_at']


class TransactionDetailSerializer(TransactionSerializer):
    """Detailed serializer for transactions"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    
    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + ['user', 'user_name',
                  'campaign', 'campaign_title', 'phone_number', 'mpesa_receipt',
                  'payhero_reference', 'payhero_checkout_id', 'metadata']


class MpesaPaymentSerializer(serializers.Serializer):
    """Serializer for initiating M-Pesa payment"""
    campaign_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=10)
    phone_number = serializers.CharField(max_length=15)
    is_anonymous = serializers.BooleanField(default=False)
    
    def validate_phone_number(self, value):
        # Basic phone validation for Kenya
        if not value.startswith('0') and not value.startswith('254'):
            raise serializers.ValidationError("Phone number must start with 0 or 254")
        return value


class CardPaymentSerializer(serializers.Serializer):
    """Serializer for initiating card payment"""
    campaign_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=10)
    card_token = serializers.CharField()
    is_anonymous = serializers.BooleanField(default=False)


class ContributionSerializer(serializers.ModelSerializer):
    """Serializer for contributions"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    
    class Meta:
        model = Contribution
        fields = ['id', 'user', 'user_name', 'campaign', 'campaign_title',
                  'amount', 'is_anonymous', 'created_at']
        read_only_fields = ['created_at']


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for payouts"""
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    
    class Meta:
        model = Payout
        fields = ['id', 'payout_id', 'organization', 'organization_name',
                  'campaign', 'campaign_title', 'amount', 'currency',
                  'status', 'created_at', 'processed_at']
        read_only_fields = ['payout_id', 'status', 'created_at', 'processed_at']


class PayoutInitiateSerializer(serializers.Serializer):
    """Serializer for initiating payout"""
    organization_id = serializers.IntegerField()
    campaign_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)