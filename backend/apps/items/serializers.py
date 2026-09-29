from rest_framework import serializers
from django.db.models import Avg
from .models import Item, Category, ItemImage, ItemSuggestion
from apps.reviews.models import Review

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon']

class ItemImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemImage
        fields = ['id', 'image', 'is_primary', 'caption']

class ItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    steward_name = serializers.CharField(source='steward.username', read_only=True)
    images = ItemImageSerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()
    item_reviews_count = serializers.SerializerMethodField()
    item_reviews_avg = serializers.SerializerMethodField()

    def get_primary_image(self, obj):
        return obj.display_image_url

    def get_item_reviews_count(self, obj):
        annotated_count = getattr(obj, 'item_reviews_count', None)
        if annotated_count is not None:
            return int(annotated_count)
        return Review.objects.filter(booking__item=obj).count()

    def get_item_reviews_avg(self, obj):
        annotated_avg = getattr(obj, 'item_reviews_avg', None)
        if annotated_avg is not None:
            return round(float(annotated_avg), 2) if annotated_avg else 0
        avg = Review.objects.filter(booking__item=obj).aggregate(avg=Avg('rating'))['avg'] or 0
        return round(float(avg), 2)
    
    class Meta:
        model = Item
        fields = [
            'id', 'name', 'slug', 'description', 'category', 'category_name',
            'steward', 'steward_name', 'condition', 'status', 'location_details',
            'daily_rate', 'deposit_amount', 'max_borrow_days', 'total_bookings',
            'primary_image', 'images', 'item_reviews_count', 'item_reviews_avg',
            'created_at', 'updated_at'
        ]


class ItemSuggestionSerializer(serializers.ModelSerializer):
    suggested_by_username = serializers.CharField(source='suggested_by.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    user_has_voted = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ItemSuggestion
        fields = [
            'id',
            'name',
            'description',
            'estimated_cost',
            'category',
            'category_name',
            'image',
            'image_url',
            'votes',
            'status',
            'created_at',
            'updated_at',
            'suggested_by_username',
            'user_has_voted',
        ]
        read_only_fields = [
            'votes',
            'status',
            'created_at',
            'updated_at',
            'suggested_by_username',
            'user_has_voted',
        ]

    def get_user_has_voted(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.voters.filter(id=request.user.id).exists()

    def get_image_url(self, obj):
        if obj.image:
            try:
                return obj.image.url
            except ValueError:
                return ''
        return ''


class ItemSuggestionCreateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ItemSuggestion
        fields = ['name', 'description', 'estimated_cost', 'category', 'category_name', 'image']

    def validate_estimated_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Estimated cost cannot be negative.')
        return value

    def validate(self, attrs):
        category = attrs.get('category')
        category_name = attrs.get('category_name', '').strip()

        if not category and category_name:
            matched_category = Category.objects.filter(name__iexact=category_name).first()
            if matched_category:
                attrs['category'] = matched_category

        if attrs.get('estimated_cost') is None:
            attrs['estimated_cost'] = 0

        attrs.pop('category_name', None)
        return attrs