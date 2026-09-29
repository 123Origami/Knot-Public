from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Avg
from .models import Review
from .serializers import ReviewSerializer, ReviewCreateSerializer, ReviewResponseSerializer

class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for reviews"""
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action == 'respond':
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReviewCreateSerializer
        return ReviewSerializer
    
    def get_queryset(self):
        queryset = Review.objects.all()
        
        # Filter by user
        user_id = self.request.query_params.get('user', None)
        if user_id:
            queryset = queryset.filter(reviewee_id=user_id)
        
        # Filter by booking
        booking_id = self.request.query_params.get('booking', None)
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def respond(self, request, pk=None):
        """Respond to a review"""
        review = self.get_object()
        
        # Check permission (only reviewee can respond)
        if review.reviewee != request.user:
            return Response(
                {'error': 'Only the reviewee can respond to this review'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ReviewResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        review.add_response(serializer.validated_data['response'])
        
        return Response({'status': 'response added'})


class UserReviewStatsView(generics.RetrieveAPIView):
    """Get review statistics for a user"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, user_id):
        reviews = Review.objects.filter(reviewee_id=user_id)
        
        stats = {
            'total_reviews': reviews.count(),
            'average_rating': reviews.aggregate(Avg('rating'))['rating__avg'] or 0,
            'rating_counts': {
                5: reviews.filter(rating=5).count(),
                4: reviews.filter(rating=4).count(),
                3: reviews.filter(rating=3).count(),
                2: reviews.filter(rating=2).count(),
                1: reviews.filter(rating=1).count(),
            }
        }
        
        return Response(stats)