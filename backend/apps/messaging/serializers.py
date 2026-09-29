from rest_framework import serializers
from .models import Conversation, Message
from apps.accounts.serializers import UserSerializer

class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages"""
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_name', 'content', 'is_read', 'created_at']
        read_only_fields = ['sender', 'is_read', 'created_at']


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating messages"""
    
    class Meta:
        model = Message
        fields = ['content']


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for conversations"""
    last_message = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ['id', 'subject', 'participants', 'last_message',
                  'other_participant', 'unread_count', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        message = obj.last_message()
        if message:
            return MessageSerializer(message).data
        return None
    
    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            other = obj.get_other_participant(request.user)
            if other:
                return UserSerializer(other).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.messages.filter(
                ~Q(sender=request.user),
                is_read=False
            ).count()
        return 0


class ConversationDetailSerializer(ConversationSerializer):
    """Detailed serializer with messages"""
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages', 'related_item', 'related_booking']


class ConversationCreateSerializer(serializers.Serializer):
    """Serializer for creating a new conversation"""
    recipient_id = serializers.IntegerField()
    subject = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField()
    item_id = serializers.IntegerField(required=False, allow_null=True)
    booking_id = serializers.IntegerField(required=False, allow_null=True)