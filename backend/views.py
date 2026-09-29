from django.contrib.auth.decorators import login_required
from apps.accounts.decorators import email_verified_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout as auth_logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count
from apps.campaigns.models import Campaign
from apps.items.models import Item, ItemSuggestion
from apps.bookings.models import Booking
from apps.messaging.models import Message
from apps.accounts.models import CustomUser
from django.db.models import Avg


def index(request):
    # Featured items: most-booked or highest-rated
    featured_items_qs = (
        Item.objects.filter()
        .annotate(avg_rating=Avg('bookings__reviews__rating'))
        .order_by('-total_bookings', '-avg_rating')[:6]
    )

    featured_items = []
    for it in featured_items_qs:
        img = it.images.first() if hasattr(it, 'images') else None
        featured_items.append({
            'id': it.id,
            'name': it.name,
            'slug': getattr(it, 'slug', ''),
            'description': getattr(it, 'description', '')[:160],
            'category': getattr(it.category, 'name', '') if getattr(it, 'category', None) else '',
            'price': getattr(it, 'daily_rate', 0),
            'rating': round(getattr(it, 'avg_rating', 0) or 0, 2),
            'image_url': img.image.url if img and getattr(img, 'image', None) else '',
        })

    # Active campaigns
    active_campaigns_qs = Campaign.objects.filter(status='active').order_by('-funds_raised')[:4]
    active_campaigns = []
    for c in active_campaigns_qs:
        percent = 0
        try:
            if c.target_amount and c.target_amount > 0:
                percent = min(100, int((c.funds_raised or 0) / c.target_amount * 100))
        except Exception:
            percent = 0
        active_campaigns.append({
            'id': c.id,
            'title': c.title,
            'status': c.status,
            'funds_raised': c.funds_raised or 0,
            'target_amount': c.target_amount or 0,
            'percent': percent,
        })

    # Lightweight site stats
    total_users = CustomUser.objects.count()
    total_items = Item.objects.count()
    total_campaigns = Campaign.objects.count()

    context = {
        'featured_items': featured_items,
        'active_campaigns': active_campaigns,
        'stats': {
            'users': total_users,
            'items': total_items,
            'campaigns': total_campaigns,
        }
    }
    return render(request, 'index.html', context)

def login(request):
    return render(request, 'registration/login.html')

def signup(request):
    return render(request, 'registration/signup.html')

def admin(request):
    return render (request, 'admin.html')

@login_required
@email_verified_required
def browse(request):
    """Browse items page - only accessible if email verified"""
    return render(request, 'browse.html')

@login_required
@email_verified_required
def goals(request):
    """Community goals page - only accessible if email verified"""
    return render(request, 'goals.html')

def item_detail(request):
    return render(request, 'item-detail.html')


@login_required
@email_verified_required
def book_item(request, item_id):
    """Legacy booking route. Redirect to canonical slug booking page."""
    item = get_object_or_404(Item, id=item_id)
    return redirect('book_item_slug', slug=item.slug)


@login_required
@email_verified_required
def suggest(request):
    """Suggest item page - only accessible if email verified"""
    suggestions = ItemSuggestion.objects.select_related('suggested_by', 'category').all()
    voteable_suggestions = suggestions.exclude(status='pending')
    context = {
        'suggestions': suggestions.order_by('-votes', '-created_at')[:20],
        'voteable_suggestions': voteable_suggestions.order_by('-votes', '-created_at')[:20],
        'top_suggestions': voteable_suggestions.order_by('-votes', '-created_at')[:3],
        'timeline_suggestions': suggestions.order_by('-updated_at')[:6],
        'my_suggestions': suggestions.filter(suggested_by=request.user).order_by('-created_at')[:5],
    }
    return render(request, 'suggest.html', context)



@login_required
@email_verified_required
def user_dashboard(request):
    """Regular user dashboard"""
    from apps.bookings.models import Booking
    from apps.bookings.services import sync_overdue_bookings_for_user, get_unreturned_overdue_bookings_for_borrower
    from apps.items.models import Item, ItemSuggestion, Category
    from apps.core.models import Notification
    from apps.payments.models import Contribution
    from django.db.models import Sum

    # Keep booking statuses up to date for this user and trigger overdue notifications.
    sync_overdue_bookings_for_user(request.user)
    
    # User bookings
    all_user_bookings = Booking.objects.filter(borrower=request.user).select_related('item').prefetch_related('item__images').order_by('-created_at')
    active_bookings = all_user_bookings.filter(status__in=['approved', 'paid', 'active']).count()
    past_bookings = all_user_bookings.filter(status__in=['completed', 'cancelled', 'declined']).count()
    
    # Borrowed item history for MVP (no member-owned item management)
    borrowed_item_history = []
    borrowed_item_index = {}
    for booking in all_user_bookings:
        item_id = booking.item_id
        entry = borrowed_item_index.get(item_id)
        if not entry:
            entry = {
                'item': booking.item,
                'booking_count': 0,
                'latest_status': booking.get_status_display(),
                'last_booking_date': booking.end_date,
            }
            borrowed_item_index[item_id] = entry
            borrowed_item_history.append(entry)

        entry['booking_count'] += 1
        if booking.end_date and (not entry['last_booking_date'] or booking.end_date > entry['last_booking_date']):
            entry['last_booking_date'] = booking.end_date

    borrowed_items_count = len(borrowed_item_index)

    available_categories = Category.objects.order_by('name')
    
    # User suggestions
    my_suggestions = ItemSuggestion.objects.filter(suggested_by=request.user).order_by('-created_at')

    # User contributions
    my_contributions = Contribution.objects.filter(user=request.user).select_related('campaign').order_by('-created_at')
    total_contributed = my_contributions.aggregate(total=Sum('amount'))['total'] or 0

    # Borrowed and lent item snapshots
    borrowed_items = all_user_bookings.filter(status__in=['approved', 'paid', 'active']).select_related('item')[:5]
    completed_borrowed_items = all_user_bookings.filter(status='completed').select_related('item')[:5]

    pending_borrower_reviews = list(
        Booking.objects.filter(
            borrower=request.user,
            status='completed',
        )
        .exclude(reviews__reviewer=request.user, reviews__review_type='borrower_to_steward')
        .select_related('item', 'item__steward')
        .order_by('-updated_at')[:8]
    )

    pending_borrower_review_ids = [booking.id for booking in pending_borrower_reviews]
    pending_reviews_count = len(pending_borrower_reviews)

    overdue_blocking_bookings = list(
        get_unreturned_overdue_bookings_for_borrower(request.user)
        .select_related('item')
        .order_by('end_date')
    )

    # Notifications
    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    # Lightweight recent activity feed
    recent_activity = []
    for booking in all_user_bookings[:4]:
        recent_activity.append({
            'type': 'booking',
            'title': f'Booking {booking.get_status_display()}',
            'description': f'{booking.item.name} ({booking.start_date} to {booking.end_date})',
            'timestamp': booking.created_at,
        })
    for suggestion in my_suggestions[:3]:
        recent_activity.append({
            'type': 'suggestion',
            'title': f'Suggestion: {suggestion.name}',
            'description': f'Status: {suggestion.get_status_display()} • Votes: {suggestion.votes}',
            'timestamp': suggestion.created_at,
        })
    for contribution in my_contributions[:3]:
        recent_activity.append({
            'type': 'contribution',
            'title': f'Contributed Ksh {contribution.amount}',
            'description': f'To goal: {contribution.campaign.title}',
            'timestamp': contribution.created_at,
        })
    recent_activity = sorted(recent_activity, key=lambda x: x['timestamp'], reverse=True)[:10]

    booking_ids = list(all_user_bookings.values_list('id', flat=True))
    unread_counts_qs = Message.objects.filter(
        conversation__related_booking_id__in=booking_ids,
        conversation__participants=request.user,
        is_read=False,
    ).exclude(sender=request.user).values('conversation__related_booking_id').annotate(total=Count('id'))
    booking_chat_unread_counts = {
        row['conversation__related_booking_id']: row['total']
        for row in unread_counts_qs
    }

    all_user_bookings_list = list(all_user_bookings)
    for booking in all_user_bookings_list:
        booking.chat_unread_count = booking_chat_unread_counts.get(booking.id, 0)
    
    context = {
        'user': request.user,
        'active_bookings': active_bookings,
        'past_bookings': past_bookings,
        'borrowed_items_count': borrowed_items_count,
        'available_categories': available_categories,
        'total_contributed': total_contributed,
        'recent_activity': recent_activity,
        'borrowed_items': borrowed_items,
        'completed_borrowed_items': completed_borrowed_items,
        'suggestions': my_suggestions,
        'borrowed_item_history': borrowed_item_history,
        'my_contributions': my_contributions,
        'all_user_bookings': all_user_bookings_list,
        'user_bookings': all_user_bookings_list[:5],
        'pending_borrower_reviews': pending_borrower_reviews,
        'pending_borrower_review_ids': pending_borrower_review_ids,
        'pending_reviews_count': pending_reviews_count,
        'overdue_blocking_bookings': overdue_blocking_bookings,
        'overdue_blocking_count': len(overdue_blocking_bookings),
        'recent_notifications': recent_notifications,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'dashboard.html', context)

@login_required
@email_verified_required
def admin_dashboard_view(request):
    """Admin dashboard view"""
    # Check if user is admin
    if not (request.user.is_superuser or request.user.is_staff or request.user.is_admin_approved):
        messages.error(request, 'You do not have permission to access the admin dashboard.')
        return redirect('user_dashboard')
    
    # You can reuse your existing admin_dashboard function or call it
    from apps.accounts.views import admin_dashboard
    return admin_dashboard(request)

@login_required
@email_verified_required
def profile_view(request):
    """User profile page - only accessible if email verified"""
    if request.user.is_admin_approved:
        template = 'admin/profile.html'
    else:
        template = 'profile.html'
    return render(request, template, {'user': request.user})

def logout_view(request):
    """Log out user"""
    auth_logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('index')






def campaign_detail(request, campaign_id):
    """Display a single campaign page"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    return render(request, 'campaign_detail.html', {'campaign': campaign})


def info_page(request, page_key):
    """Render simple informational pages used by footer and auth links."""
    pages = {
        'how-it-works': {
            'title': 'How It Works',
            'heading': 'How Knot Works',
            'body': 'Knot helps neighbors share useful items through trusted booking, transparent scheduling, and community-first stewardship.',
        },
        'help-center': {
            'title': 'Help Center',
            'heading': 'Help Center',
            'body': 'Need support? Start by checking booking status, account verification, and campaign contribution updates in your dashboard.',
        },
        'community-guidelines': {
            'title': 'Community Guidelines',
            'heading': 'Community Guidelines',
            'body': 'Use items responsibly, communicate clearly, return items on time, and report any issues through official channels.',
        },
        'safety-tips': {
            'title': 'Safety Tips',
            'heading': 'Safety Tips',
            'body': 'Inspect items before use, follow manufacturer instructions, and avoid unsafe operation. Safety always comes first.',
        },
        'contact-us': {
            'title': 'Contact Us',
            'heading': 'Contact Us',
            'body': 'For account or booking support, contact the Knot admin team. Include your booking ID or username for faster help.',
        },
        'terms-of-service': {
            'title': 'Terms of Service',
            'heading': 'Terms of Service',
            'body': 'By using Knot, you agree to respectful platform use, truthful account details, and compliance with booking and contribution rules.',
        },
        'privacy-policy': {
            'title': 'Privacy Policy',
            'heading': 'Privacy Policy',
            'body': 'Knot stores only required account and activity data to provide platform services, improve trust, and keep records accurate.',
        },
        'cookie-policy': {
            'title': 'Cookie Policy',
            'heading': 'Cookie Policy',
            'body': 'Knot uses essential cookies for authentication, session state, and secure navigation across pages.',
        },
    }

    page = pages.get(page_key)
    if not page:
        return redirect('index')

    context = {
        'page_title': page['title'],
        'page_heading': page['heading'],
        'page_body': page['body'],
    }
    return render(request, 'info_page.html', context)