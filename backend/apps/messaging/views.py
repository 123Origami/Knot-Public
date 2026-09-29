from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Conversation, Message
from .serializers import (
    ConversationSerializer, ConversationDetailSerializer,
    ConversationCreateSerializer, MessageSerializer, MessageCreateSerializer
)
from apps.accounts.models import CustomUser
from apps.items.models import Item
from apps.bookings.models import Booking

class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet for conversations"""
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    
    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConversationDetailSerializer
        elif self.action == 'create':
            return ConversationCreateSerializer
        return ConversationSerializer
    
    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Conversation.objects.none()
        
        # User can only see conversations they're part of
        return Conversation.objects.filter(
            participants=user
        ).order_by('-updated_at')
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Get recipient
        recipient = get_object_or_404(CustomUser, id=data['recipient_id'])
        
        # Check if conversation already exists
        existing = Conversation.objects.filter(
            participants=request.user
        ).filter(participants=recipient).first()
        
        if existing:
            # Add message to existing conversation
            message = Message.objects.create(
                conversation=existing,
                sender=request.user,
                content=data['message']
            )
            serializer = ConversationDetailSerializer(existing, context={'request': request})
            return Response(serializer.data)
        
        # Create new conversation
        conversation = Conversation.objects.create(
            subject=data.get('subject', ''),
        )
        
        # Add participants
        conversation.participants.add(request.user, recipient)
        
        # Link to related objects if provided
        if data.get('item_id'):
            item = get_object_or_404(Item, id=data['item_id'])
            conversation.related_item = item
            if not conversation.subject:
                conversation.subject = f"Inquiry about {item.name}"
        
        if data.get('booking_id'):
            booking = get_object_or_404(Booking, id=data['booking_id'])
            conversation.related_booking = booking
            if not conversation.subject:
                conversation.subject = f"Booking {booking.booking_id}"
        
        conversation.save()
        
        # Create initial message
        Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=data['message']
        )
        
        response_serializer = ConversationDetailSerializer(conversation, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message in a conversation"""
        conversation = self.get_object()
        
        # Check if user is participant
        if request.user not in conversation.participants.all():
            return Response(
                {'error': 'You are not a participant in this conversation'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=serializer.validated_data['content']
        )
        
        # Update conversation timestamp
        conversation.save()  # This will update updated_at
        
        response_serializer = MessageSerializer(message)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark all messages in conversation as read"""
        conversation = self.get_object()
        
        # Mark messages not sent by user as read
        unread = conversation.messages.filter(
            ~Q(sender=request.user),
            is_read=False
        )
        
        for message in unread:
            message.mark_as_read()
        
        return Response({'status': f'{unread.count()} messages marked as read'})


class MessageViewSet(viewsets.ModelViewSet):
    """ViewSet for messages"""
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Users can only see messages from their conversations
        return Message.objects.filter(
            conversation__participants=self.request.user
        ).order_by('created_at')