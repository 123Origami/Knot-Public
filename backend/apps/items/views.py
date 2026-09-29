from rest_framework import generics, permissions, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.db.models import Q, Count, Avg
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.urls import reverse
from .models import Item, Category, ItemSuggestion
from .serializers import (
    ItemSerializer,
    CategorySerializer,
    ItemSuggestionSerializer,
    ItemSuggestionCreateSerializer,
)
from apps.bookings.models import Booking
from apps.bookings.services import get_unreturned_overdue_bookings_for_borrower
from apps.reviews.models import Review
from datetime import datetime
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json

from apps.campaigns.models import Campaign, Organization
from apps.core.models import Notification


BLOCKING_BOOKING_STATUSES = ['pending', 'approved', 'paid', 'active', 'overdue']


def _format_ksh(value):
    try:
        amount = Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        return '0.00'
    return f"{amount:,.2f}"


def _build_goal_published_notification(campaign):
    category_name = campaign.category.name if campaign.category else 'General'
    return {
        'title': f'Goal Published: {campaign.title}',
        'message': (
            'Great news! Your community suggestion is now live as a fundraising goal.\n'
            f'Goal: {campaign.title}\n'
            f'Target Amount: Ksh {_format_ksh(campaign.target_amount)}\n'
            f'Category: {category_name}\n'
            'Next Step: Open Campaigns to follow progress and contributions.'
        ),
        'related_url': reverse('campaign_detail', args=[campaign.id]),
    }


def _notify_goal_published(suggestion, campaign):
    payload = _build_goal_published_notification(campaign)
    recipients = set(suggestion.voters.all())
    if suggestion.suggested_by_id:
        recipients.add(suggestion.suggested_by)

    for user in recipients:
        Notification.objects.create(
            user=user,
            notification_type='system',
            title=payload['title'],
            message=payload['message'],
            related_url=payload['related_url'],
        )


def _resolve_category_for_suggestion(category_id, new_category_name, fallback_category):
    new_category_name = (new_category_name or '').strip()
    if new_category_name:
        existing = Category.objects.filter(name__iexact=new_category_name).first()
        if existing:
            return existing

        base_slug = slugify(new_category_name) or 'category'
        candidate_slug = base_slug
        index = 1
        while Category.objects.filter(slug=candidate_slug).exists():
            candidate_slug = f'{base_slug}-{index}'
            index += 1

        return Category.objects.create(name=new_category_name, slug=candidate_slug)

    if category_id:
        return get_object_or_404(Category, id=category_id)

    return fallback_category


def _sync_stale_borrowed_items():
    """Reset borrowed items to available when they no longer have blocking bookings."""
    blocking_item_ids = Booking.objects.filter(
        status__in=BLOCKING_BOOKING_STATUSES,
    ).values_list('item_id', flat=True).distinct()

    Item.objects.filter(status='borrowed').exclude(id__in=blocking_item_ids).update(status='available')


class ItemListView(generics.ListAPIView):
    """List all items with filtering"""
    serializer_class = ItemSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        _sync_stale_borrowed_items()
        queryset = Item.objects.all()
        
        # Get filter parameters
        search = self.request.query_params.get('search', '')
        category = self.request.query_params.get('category', '')
        sort = self.request.query_params.get('sort', '-created_at')
        
        # Apply search filter
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(location_details__icontains=search)
            )
        
        # Apply category filter
        if category:
            queryset = queryset.filter(category__slug=category)

        # Ensure listing data includes accurate review metrics per item.
        queryset = queryset.annotate(
            item_reviews_count=Count('bookings__reviews', distinct=True),
            item_reviews_avg=Avg('bookings__reviews__rating'),
        )
        
        # Apply sorting
        if sort == 'daily_rate':
            queryset = queryset.order_by('daily_rate')
        elif sort == '-daily_rate':
            queryset = queryset.order_by('-daily_rate')
        elif sort == '-total_bookings':
            queryset = queryset.order_by('-total_bookings')
        else:
            queryset = queryset.order_by('-created_at')
        
        # Print debug info
        print(f"Items found: {queryset.count()}")
        print(f"Filters - search: '{search}', category: '{category}', sort: '{sort}'")
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })

class ItemDetailView(generics.RetrieveAPIView):
    """Get item details by slug"""
    serializer_class = ItemSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    def get_queryset(self):
        _sync_stale_borrowed_items()
        return Item.objects.all()


class CategoryListView(generics.ListAPIView):
    """List all categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class ItemAvailabilityView(APIView):
    """Check if an item is available for specific dates"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, item_id):
        _sync_stale_borrowed_items()
        item = get_object_or_404(Item, id=item_id)
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        is_blocked = item.status in ['maintenance', 'retired']
        
        if not start_date or not end_date:
            return Response({
                'available': not is_blocked,
                'message': 'Item is available' if not is_blocked else 'Item is not available'
            })
        
        try:
            parsed_start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            parsed_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response({'available': False, 'message': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        today = timezone.localdate()
        if parsed_start_date < today or parsed_end_date < today:
            return Response({'available': False, 'message': 'Past dates cannot be booked.'})

        if parsed_end_date < parsed_start_date:
            return Response({'available': False, 'message': 'End date cannot be before start date.'})

        # Check for overlapping bookings, considering a short buffer after existing bookings
        BUFFER_DAYS = 3
        # To ensure new bookings can only start at least BUFFER_DAYS after an existing booking's end,
        # we treat bookings as blocking up to (end_date + (BUFFER_DAYS - 1)).
        offset = timedelta(days=(BUFFER_DAYS - 1))
        overlapping = Booking.objects.filter(
            item=item,
            status__in=BLOCKING_BOOKING_STATUSES,
            start_date__lte=parsed_end_date,
            end_date__gte=(parsed_start_date - offset)
        ).exists()
        
        return Response({
            'available': not is_blocked and not overlapping,
            'item_id': item.id,
            'name': item.name,
            'start_date': start_date,
            'end_date': end_date
        })

class ItemStatsView(APIView):
    """Get item statistics"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        total_items = Item.objects.count()
        available_items = Item.objects.filter(status='available').count()
        borrowed_items = Item.objects.filter(status='borrowed').count()
        categories = Category.objects.count()
        
        # Most borrowed items
        most_borrowed = Item.objects.order_by('-total_bookings')[:5]
        most_borrowed_data = ItemSerializer(most_borrowed, many=True).data
        
        return Response({
            'total_items': total_items,
            'available_items': available_items,
            'borrowed_items': borrowed_items,
            'categories': categories,
            'most_borrowed': most_borrowed_data
        })


def _is_admin_user(user):
    return bool(
        user.is_authenticated and (
            user.is_superuser or
            user.is_staff or
            getattr(user, 'is_admin_approved', False)
        )
    )


class SuggestionListCreateView(APIView):
    """List suggestions and allow authenticated users to submit a suggestion."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        status_filter = request.query_params.get('status')
        queryset = ItemSuggestion.objects.select_related('suggested_by', 'category').all()

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.exclude(status='rejected')

        serializer = ItemSuggestionSerializer(queryset, many=True, context={'request': request})
        return Response({'count': queryset.count(), 'results': serializer.data})

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = ItemSuggestionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        suggestion = serializer.save(suggested_by=request.user)
        response_data = ItemSuggestionSerializer(suggestion, context={'request': request}).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class SuggestionVoteToggleView(APIView):
    """Toggle a vote on a suggestion for the current user."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, suggestion_id):
        suggestion = get_object_or_404(ItemSuggestion, id=suggestion_id)

        if suggestion.status == 'pending':
            return Response(
                {'error': 'This suggestion is not open for voting until it is approved by an admin.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if suggestion.voters.filter(id=request.user.id).exists():
            suggestion.remove_vote(request.user)
            action = 'removed'
        else:
            suggestion.add_vote(request.user)
            action = 'added'

        return Response({
            'message': f'Vote {action}.',
            'voted': action == 'added',
            'votes': suggestion.votes,
            'suggestion_id': suggestion.id,
        })


class SuggestionApproveView(APIView):
    """Admin action to approve a suggestion."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, suggestion_id):
        if not _is_admin_user(request.user):
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        suggestion = get_object_or_404(ItemSuggestion, id=suggestion_id)

        edited_name = (request.data.get('name') or suggestion.name or '').strip()
        edited_description = (request.data.get('description') or suggestion.description or '').strip()
        category_id = (request.data.get('category') or '').strip()
        new_category_name = (request.data.get('new_category_name') or '').strip()

        try:
            edited_estimated_cost = Decimal(str(request.data.get('estimated_cost') if request.data.get('estimated_cost') is not None else suggestion.estimated_cost or 0))
        except (TypeError, ValueError, InvalidOperation):
            return Response({'error': 'Estimated cost must be a valid number.'}, status=status.HTTP_400_BAD_REQUEST)

        if edited_estimated_cost < 0:
            return Response({'error': 'Estimated cost cannot be negative.'}, status=status.HTTP_400_BAD_REQUEST)

        target_amount_raw = request.data.get('target_amount')
        if target_amount_raw in (None, ''):
            target_amount = edited_estimated_cost if edited_estimated_cost > 0 else Decimal('1000.00')
        else:
            try:
                target_amount = Decimal(str(target_amount_raw))
            except (TypeError, ValueError):
                return Response({'error': 'Target amount must be a valid number.'}, status=status.HTTP_400_BAD_REQUEST)

        if target_amount <= 0:
            return Response({'error': 'Target amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

        category = _resolve_category_for_suggestion(category_id, new_category_name, suggestion.category)
        image_file = request.FILES.get('image')
        suggestion_image = image_file if image_file else suggestion.image

        campaign = Campaign.objects.filter(suggested_item=suggestion).first()
        campaign_created_now = campaign is None

        if not campaign:
            host_organization = Organization.objects.filter(is_active=True).order_by('id').first()
            if not host_organization:
                host_organization = Organization.objects.create(
                    name='Knot Community Hub',
                    description='Auto-generated default host for community campaigns.',
                    address='To be updated',
                    contact_email='noreply@knot.local',
                    contact_phone='0700000000',
                    is_verified=False,
                    is_active=True,
                )

            campaign = Campaign.objects.create(
                title=edited_name,
                description=edited_description,
                image=suggestion_image,
                target_amount=target_amount,
                min_contribution=Decimal('10.00'),
                suggested_item=suggestion,
                category=category,
                created_by=request.user,
                host_organization=host_organization,
                start_date=timezone.now(),
                end_date=timezone.now() + timedelta(days=30),
                status='active',
            )
        else:
            campaign.title = edited_name
            campaign.description = edited_description
            campaign.target_amount = target_amount
            campaign.category = category
            campaign.status = 'active'
            update_fields = ['title', 'description', 'target_amount', 'category', 'status', 'updated_at']
            if image_file:
                campaign.image = image_file
                update_fields.append('image')
            elif not campaign.image and suggestion.image:
                campaign.image = suggestion.image
                update_fields.append('image')
            campaign.save(update_fields=update_fields)

        suggestion.name = edited_name
        suggestion.description = edited_description
        suggestion.estimated_cost = edited_estimated_cost
        suggestion.category = category
        if image_file:
            suggestion.image = image_file
        suggestion.status = 'campaign_created'
        suggestion_update_fields = ['name', 'description', 'estimated_cost', 'category', 'status', 'updated_at']
        if image_file:
            suggestion_update_fields.append('image')
        suggestion.save(update_fields=suggestion_update_fields)

        _notify_goal_published(suggestion, campaign)

        if campaign_created_now:
            response_message = 'Suggestion updated, approved, and published to Community Goals.'
        else:
            response_message = 'Campaign updated successfully.'

        return Response({
            'message': response_message,
            'suggestion_id': suggestion.id,
            'status': suggestion.status,
            'campaign_id': campaign.id,
            'campaign_title': campaign.title,
            'campaign_url': reverse('campaign_detail', args=[campaign.id]),
            'campaign_image_url': campaign.image.url if campaign.image else '',
        })


class SuggestionDeleteView(APIView):
    """Admin action to delete a suggestion."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, suggestion_id):
        if not _is_admin_user(request.user):
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        suggestion = get_object_or_404(ItemSuggestion, id=suggestion_id)
        
        # Check if suggestion has a campaign (was published)
        has_campaign = suggestion.status == 'campaign_created'
        campaign_title = None
        cancelled_campaign = False
        
        if has_campaign:
            campaign = Campaign.objects.filter(suggested_item=suggestion).first()
            if campaign:
                campaign_title = campaign.title
                # Cancel the campaign if it's not already completed/funded/cancelled
                if campaign.status not in ['completed', 'cancelled']:
                    campaign.status = 'cancelled'
                    campaign.save(update_fields=['status', 'updated_at'])
                    cancelled_campaign = True
        
        suggestion.delete()

        message = 'Suggestion deleted successfully.'
        if has_campaign and campaign_title:
            if cancelled_campaign:
                message += f' Associated campaign "{campaign_title}" has been cancelled.'
            else:
                message += f' Associated campaign "{campaign_title}" remains as is.'

        return Response({'message': message})



class SuggestionRejectView(APIView):
    """Admin action to reject a suggestion."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, suggestion_id):
        if not _is_admin_user(request.user):
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            suggestion = get_object_or_404(ItemSuggestion, id=suggestion_id)
            suggestion.status = 'rejected'
            suggestion.save(update_fields=['status', 'updated_at'])

            # Notify the suggestion author
            if suggestion.suggested_by:
                try:
                    Notification.objects.create(
                        user=suggestion.suggested_by,
                        notification_type='system',
                        title='Suggestion Not Approved',
                        message=f'Your suggestion "{suggestion.name}" was not approved by our community team.\n\nWe appreciate your contribution and encourage you to submit more ideas!',
                        related_url='/suggest/',
                    )
                except Exception as e:
                    # Log the notification error but don't fail the rejection
                    pass

            return Response({
                'message': 'Suggestion rejected successfully.',
                'suggestion_id': suggestion.id,
                'status': suggestion.status,
            })
        except Exception as e:
            return Response({
                'error': f'Error rejecting suggestion: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class ItemDeleteView(APIView):
    """Admin action to delete an item."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, item_id):
        if not _is_admin_user(request.user):
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        item = get_object_or_404(Item, id=item_id)
        item.delete()

        return Response({'message': 'Item deleted successfully.'})

    
def item_detail_page(request, slug):
    """Template view for item detail page"""
    _sync_stale_borrowed_items()
    item = get_object_or_404(Item, slug=slug)
    steward_reviews_queryset = Review.objects.filter(
        reviewee=item.steward,
        review_type='borrower_to_steward'
    )
    steward_current_rating = steward_reviews_queryset.aggregate(avg=Avg('rating'))['avg'] or 0
    steward_current_total_reviews = steward_reviews_queryset.count()

    item_reviews = Review.objects.filter(
        booking__item=item,
        review_type='borrower_to_steward'
    ).select_related('reviewer').order_by('-created_at')
    item_reviews_count = item_reviews.count()
    item_reviews_avg = item_reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    item_bookings_made = Booking.objects.filter(item=item).count()

    pending_item_review_booking = None
    has_completed_booking_for_item = False
    has_submitted_item_review = False
    if request.user.is_authenticated:
        completed_bookings = Booking.objects.filter(
            item=item,
            borrower=request.user,
            status='completed'
        ).order_by('-end_date', '-id')

        has_completed_booking_for_item = completed_bookings.exists()

        for booking in completed_bookings:
            already_reviewed = Review.objects.filter(
                booking=booking,
                reviewer=request.user,
                review_type='borrower_to_steward'
            ).exists()
            if already_reviewed:
                has_submitted_item_review = True
            if not already_reviewed:
                pending_item_review_booking = booking
                break
    
    # Get booked dates for availability
    booked_dates = Booking.objects.filter(
        item=item,
        status__in=BLOCKING_BOOKING_STATUSES
    ).values_list('start_date', 'end_date')
    
    # Build list of unavailable dates
    unavailable_dates = []
    for start_date, end_date in booked_dates:
        current_date = start_date
        while current_date <= end_date:
            unavailable_dates.append(current_date.strftime('%Y-%m-%d'))
            current_date += timedelta(days=1)
    
    # Prepare item data for JavaScript
    item_data = {
        'id': item.id,
        'name': item.name,
        'dailyRate': float(item.daily_rate) if item.daily_rate else 0,
        'depositAmount': float(item.deposit_amount) if item.deposit_amount else 0,
        'unavailableDates': unavailable_dates,
        'status': item.status,
        'description': item.description,
        'location_details': item.location_details,
        'max_borrow_days': item.max_borrow_days,
        'steward': {
            'username': item.steward.username,
            'full_name': item.steward.get_full_name(),
            'date_joined': item.steward.date_joined.strftime('%B %Y'),
            'average_rating': float(steward_current_rating),
            'total_reviews': steward_current_total_reviews,
        },
        'total_bookings': item.total_bookings,
        'bookings_made': item_bookings_made,
        'primary_image': item.images.filter(is_primary=True).first().image.url if item.images.filter(is_primary=True).exists() else None,
        'images': [{'url': img.image.url} for img in item.images.all()]
    }
    
    return render(request, 'item-detail.html', {
        'item': item,
        'item_data_json': json.dumps(item_data),
        'item_reviews': item_reviews,
        'item_reviews_count': item_reviews_count,
        'item_reviews_avg': round(float(item_reviews_avg), 2),
        'item_bookings_made': item_bookings_made,
        'steward_current_rating': round(float(steward_current_rating), 2),
        'steward_current_total_reviews': steward_current_total_reviews,
        'pending_item_review_booking': pending_item_review_booking,
        'has_completed_booking_for_item': has_completed_booking_for_item,
        'has_submitted_item_review': has_submitted_item_review,
    })




def book_item_page(request, slug):
    """Booking page for an item"""
    _sync_stale_borrowed_items()
    item = get_object_or_404(Item, slug=slug)

    if request.user.is_authenticated:
        overdue_qs = get_unreturned_overdue_bookings_for_borrower(request.user)
        if overdue_qs.exists():
            messages.error(
                request,
                'You cannot make a new booking while you still have overdue items pending return.'
            )
            return redirect('user_dashboard')

    if item.status == 'borrowed':
        has_blocking_booking = Booking.objects.filter(
            item=item,
            status__in=BLOCKING_BOOKING_STATUSES
        ).exists()
        if not has_blocking_booking:
            item.status = 'available'
            item.save(update_fields=['status'])

    if item.status in ['maintenance', 'retired']:
        messages.warning(request, f'{item.name} is currently {item.get_status_display().lower()} and cannot be booked right now.')
        return redirect('item-detail', slug=item.slug)
    
    # Get booked dates and buffer days (buffer prevents immediate re-booking)
    BUFFER_DAYS = 3
    booked_qs = Booking.objects.filter(
        item=item,
        status__in=BLOCKING_BOOKING_STATUSES
    ).values_list('start_date', 'end_date')

    booked_dates = []
    buffer_dates = []
    for booking in booked_qs:
        start = booking[0]
        end = booking[1]
        # add booked days
        current = start
        while current <= end:
            booked_dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)

        # add buffer days after end_date (these days are blocked until buffer expires)
        for i in range(1, BUFFER_DAYS):
            bd = end + timedelta(days=i)
            buffer_dates.append(bd.strftime('%Y-%m-%d'))

    # Remove duplicates and sort
    booked_dates = sorted(list(set(booked_dates)))
    buffer_dates = sorted(list(set(buffer_dates)))

    context = {
        'item': item,
        'booked_dates': json.dumps(booked_dates),
        'buffer_dates': json.dumps(buffer_dates),
        'max_borrow_days': item.max_borrow_days,
    }
    return render(request, 'book-item.html', context)