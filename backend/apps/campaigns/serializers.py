from rest_framework import serializers
from .models import Campaign, Organization
from apps.payments.models import Contribution, Transaction
from apps.items.models import ItemSuggestion
from apps.accounts.serializers import UserSerializer

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'description', 'logo', 'address', 'contact_email', 'contact_phone', 'is_verified']

class CampaignSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    host_organization_name = serializers.CharField(source='host_organization.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    pulled_out_by_name = serializers.CharField(source='pulled_out_by.username', read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'title', 'slug', 'description', 'image', 'target_amount', 
            'funds_raised', 'min_contribution', 'category', 'category_name',
            'created_by', 'created_by_name', 'host_organization', 'host_organization_name',
            'start_date', 'end_date', 'status', 'contributor_count',
            'progress_percentage', 'days_remaining', 'created_at',
            'funds_pulled_out', 'pulled_out_at', 'pulled_out_by_name'
        ]
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()
    
    def get_days_remaining(self, obj):
        return obj.days_remaining()

class ContributionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)
    campaign_slug = serializers.CharField(source='campaign.slug', read_only=True)
    
    class Meta:
        model = Contribution
        fields =[
            'id', 'user', 'user_name', 'campaign', 'campaign_title',
            'campaign_slug', 'amount', 'is_anonymous', 'created_at'
        ]

class CampaignSuggestionSerializer(serializers.ModelSerializer):
    suggested_by_name = serializers.CharField(source='suggested_by.username', read_only=True)
    
    class Meta:
        model = ItemSuggestion
        fields = [
            'id', 'name', 'description', 'estimated_price', 'suggested_by',
            'suggested_by_name', 'category', 'reason', 'status', 'created_at'
        ]
        read_only_fields = ['status', 'created_at']


