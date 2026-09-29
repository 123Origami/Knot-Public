from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, login as django_login
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.db import models
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.contrib.sites.models import Site
from django.urls import reverse
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer, ProfileUpdateSerializer
from .models import CustomUser, EmailVerificationToken, PasswordResetToken
from apps.campaigns.models import Campaign
from apps.items.models import Item, ItemSuggestion, Category, ItemImage
from apps.bookings.models import Booking, BookingHistory
from apps.core.models import Notification, SiteSettings
from datetime import timedelta, datetime
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse, JsonResponse
from django.db.models.functions import TruncDate
from apps.accounts.decorators import email_verified_required
from verify_email.email_handler import ActivationMailManager
from django.template.loader import render_to_string
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.html import strip_tags
from django.utils.timesince import timesince
from urllib.parse import quote_plus
import csv
import uuid
from apps.payments.models import Transaction, Contribution
from apps.reviews.models import Review
from apps.messaging.models import Conversation, Message
import re

IMAGE_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
IMAGE_MAX_SIZE_BYTES = 5 * 1024 * 1024
ITEM_MAX_IMAGES = 12
ADMIN_ID_MAX_SIZE_BYTES = 5 * 1024 * 1024


def _build_absolute_url(request, path):
    if request is not None:
        return request.build_absolute_uri(path)
    site_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    return f'{site_url}{path}' if site_url else path


def _build_verification_link(request, token):
    return _build_absolute_url(request, reverse('verify_email', args=[token]))


def _build_reset_link(request, token):
    return _build_absolute_url(request, reverse('reset_password', args=[token]))


def _generate_email_verification_token(length=8):
    """Generate a short, user-friendly verification token for manual entry."""
    while True:
        token = uuid.uuid4().hex[:length].upper()
        if not EmailVerificationToken.objects.filter(token=token).exists():
            return token


def _create_or_rotate_email_verification_token(user):
    """Ensure a single active verification token per user and return the new token string."""
    EmailVerificationToken.objects.filter(user=user).delete()
    token = _generate_email_verification_token()
    EmailVerificationToken.objects.create(user=user, token=token)
    return token


def _find_user_by_login_identifier(identifier):
    """Resolve a user by username or email for flexible login form support."""
    identifier = (identifier or '').strip()
    if not identifier:
        return None

    return CustomUser.objects.filter(
        models.Q(username__iexact=identifier) | models.Q(email__iexact=identifier)
    ).first()


def _authenticate_with_username_or_email(request, identifier, password):
    """Authenticate using username first, then fallback to email/username lookup."""
    user = authenticate(request, username=identifier, password=password)
    if user is not None:
        return user

    candidate = _find_user_by_login_identifier(identifier)
    if candidate and candidate.check_password(password):
        # Keep disabled verified accounts blocked, but allow unverified users to reach token flow.
        if candidate.is_active or not candidate.email_verified:
            return candidate

    return None


def _file_extension(file_name):
    file_name = (file_name or '').lower()
    return file_name[file_name.rfind('.'):] if '.' in file_name else ''


def _validate_image_file(image_file, label='Image'):
    ext = _file_extension(getattr(image_file, 'name', ''))
    if ext not in IMAGE_ALLOWED_EXTENSIONS:
        return f'{label} must be JPG, PNG, or WEBP.'

    if getattr(image_file, 'size', 0) > IMAGE_MAX_SIZE_BYTES:
        return f'{label} must be 5MB or smaller.'

    return None


def _validate_image_batch(primary_image, additional_images, existing_count=0):
    additional_images = [f for f in (additional_images or []) if f]
    total_images = existing_count + (1 if primary_image else 0) + len(additional_images)
    if total_images > ITEM_MAX_IMAGES:
        if existing_count:
            return f'You can have at most {ITEM_MAX_IMAGES} images per item.'
        return f'You can upload at most {ITEM_MAX_IMAGES} images per item.'

    if primary_image:
        error = _validate_image_file(primary_image, 'Primary image')
        if error:
            return error

    for image_file in additional_images:
        error = _validate_image_file(image_file, f'File "{image_file.name}"')
        if error:
            return error

    return None


def _validate_admin_id_photo(photo_file):
    if not photo_file:
        return 'Please upload a clear photo of your ID for admin request review.'

    ext = _file_extension(getattr(photo_file, 'name', ''))
    if ext not in IMAGE_ALLOWED_EXTENSIONS:
        return 'ID photo must be JPG, PNG, or WEBP.'

    if getattr(photo_file, 'size', 0) > ADMIN_ID_MAX_SIZE_BYTES:
        return 'ID photo must be 5MB or smaller.'

    return None


def _create_category_if_needed(category_id, new_category_name):
    """Resolve category from selected ID or create one from a new name."""
    new_category_name = (new_category_name or '').strip()

    if new_category_name:
        existing_category = Category.objects.filter(name__iexact=new_category_name).first()
        if existing_category:
            return existing_category

        base_slug = slugify(new_category_name) or 'category'
        unique_slug = base_slug
        counter = 1
        while Category.objects.filter(slug=unique_slug).exists():
            unique_slug = f'{base_slug}-{counter}'
            counter += 1

        return Category.objects.create(name=new_category_name, slug=unique_slug)

    if category_id:
        return get_object_or_404(Category, id=category_id)

    return None

# ======================
# TEMPLATE-BASED VIEWS
# ======================



@csrf_protect
def signup(request):
    """Signup view for creating new accounts with email verification"""
    if request.user.is_authenticated:
        if request.user.email_verified:
            if request.user.is_admin_approved:
                return redirect('admin_dashboard')
            return redirect('user_dashboard')
        return redirect('verify_email_pending')

    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        phone_number = request.POST.get('phone_number', '')
        location = request.POST.get('location', '')
        account_type = request.POST.get('account_type', 'member')
        admin_reason = request.POST.get('admin_reason', '')
        admin_id_photo = request.FILES.get('admin_id_photo')
        
        # Validation
        if password != password2:
            messages.error(request, 'Passwords do not match')
            return redirect('signup')
        # Basic length check (min 8)
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long')
            return redirect('signup')

        # Complexity: require uppercase, lowercase, digit, special
        complexity_re = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$')
        if not complexity_re.match(password):
            messages.error(request, 'Password must include uppercase, lowercase, a digit and a special character')
            return redirect('signup')
        
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return redirect('signup')
        
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('signup')

        if account_type == 'admin' and not admin_reason.strip():
            messages.error(request, 'Please provide a reason for requesting community admin access.')
            return redirect('signup')

        if account_type == 'admin':
            id_photo_error = _validate_admin_id_photo(admin_id_photo)
            if id_photo_error:
                messages.error(request, id_photo_error)
                return redirect('signup')
        
        # Names cannot be only numbers
        if first_name and first_name.strip().isdigit():
            messages.error(request, 'First name cannot be only numbers')
            return redirect('signup')
        if last_name and last_name.strip().isdigit():
            messages.error(request, 'Last name cannot be only numbers')
            return redirect('signup')

        # Phone validation: digits only, exactly 10 characters, and unique
        phone_number = (phone_number or '').strip()
        if phone_number:
            if not phone_number.isdigit() or len(phone_number) != 10:
                messages.error(request, 'Phone number must be exactly 10 digits')
                return redirect('signup')
            if CustomUser.objects.filter(phone_number=phone_number).exists():
                messages.error(request, 'Phone number already exists')
                return redirect('signup')
        
        try:
            print("✅ Validation passed, creating user...")
            
            # Create user
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                location=location,
                # User starts inactive until email verified, unless verification is disabled site-wide
                is_active=not settings.REQUIRE_EMAIL_VERIFICATION
            )

            # Handle admin request
            if account_type == 'admin':
                user.admin_request_status = 'pending'
                user.admin_request_reason = admin_reason
                user.admin_request_id_photo = admin_id_photo
                user.admin_request_date = timezone.now()
                user.save()

            print(f"✅ User created: {user.username}")

            from django.contrib.auth import login

            if not settings.REQUIRE_EMAIL_VERIFICATION:
                user.email_verified = True
                user.verification_level = max(user.verification_level, 1)
                user.save(update_fields=['email_verified', 'verification_level'])
                if account_type == 'admin':
                    messages.success(request, 'Account created! Your admin request is pending approval — you can use your member dashboard in the meantime.')
                else:
                    messages.success(request, 'Account created! Welcome to Knot.')
                login(request, user)
                return redirect('user_dashboard')

            # Create email verification token (short code for manual entry)
            token = _create_or_rotate_email_verification_token(user)

            # Build verification link
            verification_link = _build_verification_link(request, token)

            # Send actual email
            subject = 'Verify Your Email - Knot'
            html_message = render_to_string('emails/verify_email.html', {
                'user': user,
                'link': verification_link,
                'token': token,
                'site_name': 'Knot',
                'expires_in': '30 minutes'
            })
            plain_message = strip_tags(html_message)

            try:
                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                print(f"📧 Email sent successfully to {user.email}")
                print(f"🔗 Link: {verification_link}")
                if account_type == 'admin':
                    messages.success(request, 'Account created! Verify your email with the token, then use your member dashboard while your admin request is pending approval.')
                else:
                    messages.success(request, 'Account created! Please check your email for the verification token.')
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
                print(f"🔗 Manual link: {verification_link}")
                messages.warning(request, 'Account created but email could not be sent right now. Please try resending verification from your account page.')

            # Log the user in
            login(request, user)

            return redirect('verify_email_pending')
            
        except Exception as e:
            print(f"❌ Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error creating account: {str(e)}')
            return redirect('signup')
    
    return render(request, 'registration/signup.html')




from django.contrib.auth import authenticate, login as auth_login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse

def login(request):
    """Login page view - handles both GET and POST"""
    if request.user.is_authenticated:
        if request.user.email_verified:
            if request.user.is_admin_approved:
                return redirect('admin_dashboard')
            return redirect('user_dashboard')
        return redirect('verify_email_pending')

    print("=" * 50)
    print(f"LOGIN VIEW CALLED - Method: {request.method}")
    print(f"POST data: {request.POST}")
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        login_role = request.POST.get('login_role', 'member')
        
        print(f"Username: {username}")
        print(f"Password length: {len(password) if password else 0}")
        print(f"Login role: {login_role}")
        
        # Check if username/password are empty
        if not username or not password:
            messages.error(request, 'Please enter both username and password.')
            print("ERROR: Empty username or password")
            return redirect('/login/')
        
        # Authenticate user by username or email.
        user = _authenticate_with_username_or_email(request, username, password)
        print(f"Authentication result: {user}")
        
        if user is not None:
            print(f"User found: {user.username}")
            print(f"Email verified: {user.email_verified}")
            print(f"Is active: {user.is_active}")
            print(f"Is admin approved: {user.is_admin_approved}")
            
            # Check if email is verified
            if not user.email_verified and settings.REQUIRE_EMAIL_VERIFICATION:
                if not user.is_active:
                    user.is_active = True
                    user.save(update_fields=['is_active'])
                messages.warning(request, 'Please verify your email before logging in.')
                auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                print("Redirecting to email verification pending page")
                return redirect('verify_email_pending')
            elif not user.email_verified:
                # Verification is disabled site-wide: self-heal accounts
                # created before this flag existed instead of blocking them.
                user.email_verified = True
                user.is_active = True
                user.verification_level = max(user.verification_level, 1)
                user.save(update_fields=['email_verified', 'is_active', 'verification_level'])
            
            # Log the user in
            auth_login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            
            # Role-based redirection
            if login_role == 'admin' and (user.is_admin_approved or user.is_superuser or user.is_staff):
                print("Redirecting to admin dashboard")
                return redirect('/admin-dashboard/')
            else:
                print("Redirecting to user dashboard")
                return redirect('/dashboard/')
        else:
            candidate = _find_user_by_login_identifier(username)
            if candidate and candidate.check_password(password) and candidate.email_verified and not candidate.is_active:
                messages.error(request, 'Your account is disabled. Please contact support.')
                print("ERROR: Account disabled")
                return redirect('/login/')
            messages.error(request, 'Invalid username or password.')
            print("ERROR: Authentication failed")
            return redirect('/login/')
    
    # GET request - just show the login form
    return render(request, 'registration/login.html')

# ======================
# API VIEWS (DRF)
# ======================

class RegisterView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = CustomUser.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create email verification token (short code for manual entry)
        token = _create_or_rotate_email_verification_token(user)
        
        # Send verification email (in development, print to console)
        verification_link = _build_verification_link(request, token)
        print(f"📧 Verification email: {verification_link}")
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Registration successful. Please verify your email.'
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """User login endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        # Check if this is a template form submission or API request
        if request.content_type and 'application/json' in request.content_type:
            # API request - return JSON
            serializer = LoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            
            # Check if email is verified
            if not user.email_verified and settings.REQUIRE_EMAIL_VERIFICATION:
                return Response({
                    'error': 'Email not verified',
                    'message': 'Please verify your email before logging in.',
                    'requires_verification': True,
                    'email': user.email
                }, status=status.HTTP_403_FORBIDDEN)
            elif not user.email_verified:
                user.email_verified = True
                user.is_active = True
                user.verification_level = max(user.verification_level, 1)
                user.save(update_fields=['email_verified', 'is_active', 'verification_level'])
            
            # Update last active
            user.last_active = timezone.now()
            user.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            response_data = {
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'email_verified': user.email_verified,
                'is_admin_approved': user.is_admin_approved,
                'admin_request_status': user.admin_request_status,
                'role': 'admin' if user.is_admin_approved else 'user'
            }
            
            return Response(response_data)
        else:
            # Template form submission - redirect based on role
            username = request.POST.get('username')
            password = request.POST.get('password')
            login_role = request.POST.get('login_role', 'member')
            
            # Authenticate user by username or email.
            user = _authenticate_with_username_or_email(request, username, password)
            
            if user is not None:
                # Check if email is verified
                # In the LoginView, inside the template form submission section
                if not user.email_verified and settings.REQUIRE_EMAIL_VERIFICATION:
                    if not user.is_active:
                        user.is_active = True
                        user.save(update_fields=['is_active'])
                    messages.warning(request, 'Please verify your email before logging in.')
                    from django.contrib.auth import login as django_login
                    django_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    return redirect('verify_email_pending')
                elif not user.email_verified:
                    user.email_verified = True
                    user.is_active = True
                    user.verification_level = max(user.verification_level, 1)
                    user.save(update_fields=['email_verified', 'is_active', 'verification_level'])
                
                # Check if user is trying to log in as admin but isn't one
                if login_role == 'admin' and not (user.is_superuser or user.is_staff or user.is_admin_approved):
                    messages.error(request, 'You do not have admin privileges. Please use member login.')
                    return redirect('login')
                
                # Log the user in
                from django.contrib.auth import login as django_login
                django_login(request, user)
                
                # Update last active
                user.last_active = timezone.now()
                user.save(update_fields=['last_active'])
                
                messages.success(request, f'Welcome back, {user.username}!')
                
                # Check for next parameter
                next_url = request.POST.get('next')
                if next_url:
                    return redirect(next_url)
                
                # Role-based redirection
                if login_role == 'admin' and (user.is_admin_approved or user.is_superuser or user.is_staff):
                    print("Redirecting to admin_dashboard")
                    return redirect('admin_dashboard')
                else:
                    print("Redirecting to user_dashboard")
                    return redirect('user_dashboard')
            else:
                candidate = _find_user_by_login_identifier(username)
                if candidate and candidate.check_password(password) and candidate.email_verified and not candidate.is_active:
                    messages.error(request, 'Your account is disabled. Please contact support.')
                    return redirect('login')
                messages.error(request, 'Invalid username or password.')
                return redirect('login')

class LogoutView(APIView):
    """User logout endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """User profile view and update"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class ProfileDetailView(generics.RetrieveAPIView):
    """View any user's public profile"""
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'username'


def user_profile_detail(request, username):
    """Display a user's public profile page"""
    profile_user = get_object_or_404(CustomUser, username=username)
    
    # Get user's items
    items = Item.objects.filter(steward=profile_user).order_by('-created_at')[:8]
    items_count = Item.objects.filter(steward=profile_user).count()
    
    # Get user's bookings stats
    bookings_count = Booking.objects.filter(
        Q(borrower=profile_user) | Q(item__steward=profile_user)
    ).count()
    
    # Get user's reviews and calculate average rating
    from apps.reviews.models import Review
    reviews = Review.objects.filter(
        reviewee=profile_user,
        review_type='borrower_to_steward'
    ).select_related('reviewer').order_by('-created_at')[:5]
    
    avg_rating = reviews.aggregate(avg=models.Avg('rating'))['avg'] or 0
    
    context = {
        'profile_user': profile_user,
        'items': items,
        'items_count': items_count,
        'bookings_count': bookings_count,
        'reviews': reviews,
        'avg_rating': avg_rating,
    }
    
    return render(request, 'user-detail.html', context)


class UpdateProfileView(generics.UpdateAPIView):
    """Update user profile"""
    serializer_class = ProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class VerifyEmailView(APIView):
    """Email verification endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, token):
        try:
            verification = EmailVerificationToken.objects.get(token=token)
            
            if verification.is_valid():
                user = verification.user
                user.email_verified = True
                user.verification_level = 1
                user.save()
                
                # Delete the token
                verification.delete()
                
                # Check if this is an API request or browser request
                if request.accepted_renderer.format == 'json':
                    return Response({
                        'message': 'Email verified successfully',
                        'email_verified': True,
                        'user': UserSerializer(user).data
                    })
                else:
                    # Browser request - redirect to success page
                    from django.contrib.auth import login
                    login(request, user)
                    messages.success(request, 'Email verified successfully! You can now access all features.')
                    
                    if user.is_admin_approved:
                        return redirect('admin_dashboard')
                    else:
                        return redirect('user_dashboard')
            else:
                if request.accepted_renderer.format == 'json':
                    return Response({
                        'error': 'Verification link expired',
                        'message': 'Please request a new verification email.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    messages.error(request, 'Verification link has expired. Please request a new one.')
                    return redirect('resend_verification')
                
        except EmailVerificationToken.DoesNotExist:
            if request.accepted_renderer.format == 'json':
                return Response({
                    'error': 'Invalid verification token'
                }, status=status.HTTP_404_NOT_FOUND)
            else:
                messages.error(request, 'Invalid verification link.')
                return redirect('login')

class RequestPasswordResetView(APIView):
    """Request password reset email"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return render(request, 'registration/password_reset.html')
    
    def post(self, request):
        wants_json = bool(request.content_type and 'application/json' in request.content_type)
        email = (request.data.get('email') if wants_json else request.POST.get('email')) or ''
        email = email.strip()

        if not email:
            if wants_json:
                return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
            messages.error(request, 'Please enter your email address.')
            return redirect('password_reset')

        user = CustomUser.objects.filter(email__iexact=email).first()
        if user:
            PasswordResetToken.objects.filter(user=user, used=False).delete()
            token = str(uuid.uuid4())
            PasswordResetToken.objects.create(user=user, token=token)

            reset_link = _build_reset_link(request, token)
            html_message = render_to_string('emails/password_reset.html', {
                'user': user,
                'reset_link': reset_link,
            })
            plain_message = strip_tags(html_message)

            try:
                send_mail(
                    'Reset Your Password - Knot',
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
                print(f"🔐 Password reset email sent to {user.email}: {reset_link}")
            except Exception as exc:
                print(f"❌ Failed to send password reset email: {exc}")

        generic_message = 'If an account exists for that email, a password reset link has been sent.'
        if wants_json:
            return Response({'message': generic_message})

        messages.success(request, generic_message)
        return redirect('password_reset')


class ResetPasswordView(APIView):
    """Reset password with token"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, token):
        reset_token = PasswordResetToken.objects.filter(token=token).first()
        if not reset_token or not reset_token.is_valid():
            messages.error(request, 'Password reset link is invalid or has expired.')
            return redirect('password_reset')

        return render(request, 'registration/password_reset_form.html', {'token': token})
    
    def post(self, request, token):
        wants_json = bool(request.content_type and 'application/json' in request.content_type)
        new_password = (request.data.get('new_password') if wants_json else request.POST.get('new_password')) or ''
        confirm_password = (request.data.get('confirm_password') if wants_json else request.POST.get('confirm_password')) or ''

        reset_token = PasswordResetToken.objects.filter(token=token).first()
        if not reset_token or not reset_token.is_valid():
            if wants_json:
                return Response({'error': 'Reset link expired or invalid'}, status=status.HTTP_400_BAD_REQUEST)
            messages.error(request, 'Password reset link is invalid or has expired.')
            return redirect('password_reset')

        if len(new_password) < 8:
            if wants_json:
                return Response({'error': 'Password must be at least 8 characters long.'}, status=status.HTTP_400_BAD_REQUEST)
            messages.error(request, 'Password must be at least 8 characters long.')
            return redirect('reset_password', token=token)

        if new_password != confirm_password:
            if wants_json:
                return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)
            messages.error(request, 'Passwords do not match.')
            return redirect('reset_password', token=token)

        user = reset_token.user
        user.set_password(new_password)
        user.save(update_fields=['password'])

        reset_token.used = True
        reset_token.save(update_fields=['used'])

        if wants_json:
            return Response({'message': 'Password reset successful'})

        messages.success(request, 'Password updated successfully. Please log in with your new password.')
        return redirect('login')

# ======================
# ADMIN APPROVAL VIEWS
# ======================

def is_admin(user):
    """Check if user has admin access"""
    return user.is_authenticated and (user.is_superuser or user.is_staff or 
                                     (hasattr(user, 'is_admin_approved') and user.is_admin_approved))

@user_passes_test(is_admin)
def admin_request_list(request):
    """View for admins to see pending requests"""
    pending_requests = CustomUser.objects.filter(admin_request_status='pending').order_by('-admin_request_date')
    approved_requests = CustomUser.objects.filter(admin_request_status='approved').order_by('-admin_request_review_date')
    rejected_requests = CustomUser.objects.filter(admin_request_status='rejected').order_by('-admin_request_review_date')
    
    context = {
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'rejected_requests': rejected_requests,
    }
    return render(request, 'admin/requests.html', context)

@user_passes_test(is_admin)
def admin_request_approve(request, user_id):
    """Approve an admin request"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)

        if user.admin_request_status != 'pending':
            messages.warning(request, f'Admin request for {user.username} has already been reviewed.')
            return redirect('admin_request_list')

        if not user.admin_request_id_photo:
            messages.error(request, f'Cannot approve {user.username}: no ID photo on file.')
            return redirect('admin_request_list')
        
        review_notes = (request.POST.get('notes') or '').strip()
        if not review_notes or review_notes.lower() == 'approved by admin':
            review_notes = f'Approved by {request.user.username}'

        user.admin_request_status = 'approved'
        user.is_staff = True
        user.admin_request_reviewed_by = request.user
        user.admin_request_review_date = timezone.now()
        user.admin_request_review_notes = review_notes
        user.save()
        
        messages.success(request, f'Admin request for {user.username} approved!')
        
    return redirect('admin_request_list')

@user_passes_test(is_admin)
def admin_request_reject(request, user_id):
    """Reject an admin request"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)

        if user.admin_request_status != 'pending':
            messages.warning(request, f'Admin request for {user.username} has already been reviewed.')
            return redirect('admin_request_list')
        
        review_notes = (request.POST.get('notes') or '').strip()
        if not review_notes or review_notes.lower() == 'rejected by admin':
            review_notes = f'Rejected by {request.user.username}'

        user.admin_request_status = 'rejected'
        if not user.is_superuser:
            user.is_staff = False
        user.admin_request_reviewed_by = request.user
        user.admin_request_review_date = timezone.now()
        user.admin_request_review_notes = review_notes
        user.save()
        
        messages.success(request, f'Admin request for {user.username} rejected')
        
    return redirect('admin_request_list')

@user_passes_test(is_admin)
def admin_request_bulk_action(request):
    """Handle bulk actions on admin requests"""
    if request.method == 'POST':
        action = request.POST.get('action')
        user_ids = request.POST.getlist('selected_users')
        notes = (request.POST.get('bulk_notes') or '').strip()
        
        if action == 'approve':
            users = CustomUser.objects.filter(id__in=user_ids, admin_request_status='pending')
            users_without_id = users.filter(admin_request_id_photo__isnull=True)
            users = users.exclude(admin_request_id_photo__isnull=True)
            approval_note = notes if notes else f'Approved by {request.user.username}'
            for user in users:
                user.admin_request_status = 'approved'
                user.is_staff = True
                user.admin_request_reviewed_by = request.user
                user.admin_request_review_date = timezone.now()
                user.admin_request_review_notes = approval_note
                user.save()
            messages.success(request, f'Approved {users.count()} admin requests')
            if users_without_id.exists():
                usernames = ', '.join(users_without_id.values_list('username', flat=True))
                messages.warning(request, f'Skipped users without ID photo: {usernames}')
            
        elif action == 'reject':
            users = CustomUser.objects.filter(id__in=user_ids, admin_request_status='pending')
            rejection_note = notes if notes else f'Rejected by {request.user.username}'
            for user in users:
                user.admin_request_status = 'rejected'
                if not user.is_superuser:
                    user.is_staff = False
                user.admin_request_reviewed_by = request.user
                user.admin_request_review_date = timezone.now()
                user.admin_request_review_notes = rejection_note
                user.save()
            messages.success(request, f'Rejected {users.count()} admin requests')
    
    return redirect('admin_request_list')

class ResendVerificationView(APIView):
    """Resend verification email (API endpoint)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if user.email_verified:
            return Response({
                'message': 'Email already verified',
                'email_verified': True
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Rotate token so user can always request a fresh one
        token = _create_or_rotate_email_verification_token(user)
        
        # Send verification email
        verification_link = _build_verification_link(request, token)
        print(f"📧 New verification email sent to {user.email}: {verification_link}")
        
        return Response({
            'message': 'Verification email sent successfully',
            'email_verified': False
        })

# ======================
# ADMIN DASHBOARD VIEWS
# ======================

@user_passes_test(is_admin)
def admin_dashboard(request):
    """Admin dashboard homepage"""
    from apps.items.models import Item
    from apps.items.models import ItemSuggestion
    from apps.bookings.models import Booking
    from apps.bookings.services import sync_overdue_bookings_for_user
    from apps.campaigns.models import Campaign
    from apps.reviews.models import Review
    from django.utils import timezone
    from datetime import timedelta

    sync_overdue_bookings_for_user()
    
    # User statistics
    total_users = CustomUser.objects.count()
    pending_users = CustomUser.objects.filter(admin_request_status='pending').count()
    approved_admins = CustomUser.objects.filter(admin_request_status='approved').count()
    
    # Item statistics
    total_items = Item.objects.count()
    available_items = Item.objects.filter(status='available').count()
    borrowed_items = Item.objects.filter(status='borrowed').count()
    maintenance_items = Item.objects.filter(status='maintenance').count()
    
    # Booking statistics
    active_bookings = Booking.objects.filter(status='active').count()
    pending_bookings = Booking.objects.filter(status='pending').count()
    overdue_bookings = Booking.objects.filter(status='overdue').count()
    total_bookings = Booking.objects.count()
    
    # Campaign statistics
    pending_campaigns = Campaign.objects.filter(status='active').count()
    funded_campaigns = Campaign.objects.filter(status='funded').count()
    
    # Review/Report statistics
    reported_issues = Review.objects.filter(rating__lte=2).count()  # Low ratings as issues
    
    # Active users (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    active_users = CustomUser.objects.filter(last_active__gte=last_24h).count()
    
    # Recent activity (notification-style feed)
    recent_activity = []
    feed_window = timezone.now() - timedelta(days=7)

    # Booking request notifications
    booking_requests = Booking.objects.select_related('borrower', 'item').filter(
        status='pending',
        created_at__gte=feed_window
    ).order_by('-created_at')[:8]
    for booking in booking_requests:
        recent_activity.append({
            'type': 'warning',
            'icon': 'calendar-check',
            'description': f'Booking request: {booking.borrower.username} requested {booking.item.name}',
            'timestamp': booking.created_at,
            'url': reverse('admin_booking_review', args=[booking.id])
        })

    # Suggestion notifications
    recent_suggestions = ItemSuggestion.objects.select_related('suggested_by').filter(
        created_at__gte=feed_window
    ).order_by('-created_at')[:8]
    for suggestion in recent_suggestions:
        recent_activity.append({
            'type': 'primary',
            'icon': 'lightbulb',
            'description': f'New suggestion: {suggestion.suggested_by.username} suggested {suggestion.name}',
            'timestamp': suggestion.created_at,
            'url': f"{reverse('admin_suggestions')}?q={quote_plus(suggestion.name)}"
        })

    # Campaign goal reached notifications
    funded_campaign_events = Campaign.objects.select_related('created_by').filter(
        status='funded',
        funded_date__isnull=False,
        funded_date__gte=feed_window
    ).order_by('-funded_date')[:8]
    for campaign in funded_campaign_events:
        recent_activity.append({
            'type': 'success',
            'icon': 'bullseye',
            'description': f'Goal reached: {campaign.title} hit its funding target',
            'timestamp': campaign.funded_date,
            'url': reverse('campaign_detail', args=[campaign.id])
        })
    
    # Sort activity by timestamp
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]
    
    # Pending admin requests
    pending_admin_requests = CustomUser.objects.filter(
        admin_request_status='pending'
    ).order_by('-admin_request_date')[:5]
    
    # Pending bookings that need action
    pending_bookings_list = Booking.objects.select_related('item', 'borrower', 'steward').filter(
        status='pending'
    ).order_by('-created_at')[:5]
    
    context = {
        'total_users': total_users,
        'pending_users': pending_users,
        'approved_admins': approved_admins,
        'total_items': total_items,
        'available_items': available_items,
        'borrowed_items': borrowed_items,
        'maintenance_items': maintenance_items,
        'active_borrowings': active_bookings,
        'active_bookings': active_bookings,
        'pending_bookings': pending_bookings,
        'overdue_bookings': overdue_bookings,
        'total_bookings': total_bookings,
        'pending_campaigns': pending_campaigns,
        'funded_campaigns': funded_campaigns,
        'reported_issues': reported_issues,
        'active_users': active_users,
        'recent_activity': recent_activity,
        'pending_approvals_count': pending_users + pending_bookings,
        'pending_admin_requests': pending_admin_requests,
        'pending_bookings_list': pending_bookings_list,
    }
    return render(request, 'admin/dashboard.html', context)

@user_passes_test(is_admin)
def admin_users(request):
    """User management page"""
    users_queryset = CustomUser.objects.all().order_by('-date_joined')

    query = (request.GET.get('q') or '').strip()
    verification_filter = (request.GET.get('verification') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()

    if query:
        users_queryset = users_queryset.filter(
            models.Q(username__icontains=query)
            | models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(phone_number__icontains=query)
            | models.Q(location__icontains=query)
        )

    if verification_filter.isdigit():
        users_queryset = users_queryset.filter(verification_level=int(verification_filter))

    if status_filter == 'active':
        users_queryset = users_queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        users_queryset = users_queryset.filter(is_active=False)
    elif status_filter == 'pending':
        users_queryset = users_queryset.filter(admin_request_status='pending')
    elif status_filter == 'approved':
        users_queryset = users_queryset.filter(admin_request_status='approved')

    paginator = Paginator(users_queryset, 25)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)

    context = {
        'users': users,
        'search_query': query,
        'selected_verification': verification_filter,
        'selected_status': status_filter,
        'total_count': CustomUser.objects.count(),
        'active_count': CustomUser.objects.filter(is_active=True).count(),
        'pending_admin_count': CustomUser.objects.filter(admin_request_status='pending').count(),
        'approved_admin_count': CustomUser.objects.filter(admin_request_status='approved').count(),
        'verified_count': CustomUser.objects.filter(email_verified=True).count(),
    }
    return render(request, 'admin/users.html', context)


@user_passes_test(is_admin)
def admin_users_export_csv(request):
    """Export filtered user list to CSV."""
    users_queryset = CustomUser.objects.all().order_by('-date_joined')

    query = (request.GET.get('q') or '').strip()
    verification_filter = (request.GET.get('verification') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()

    if query:
        users_queryset = users_queryset.filter(
            models.Q(username__icontains=query)
            | models.Q(first_name__icontains=query)
            | models.Q(last_name__icontains=query)
            | models.Q(email__icontains=query)
            | models.Q(phone_number__icontains=query)
            | models.Q(location__icontains=query)
        )

    if verification_filter.isdigit():
        users_queryset = users_queryset.filter(verification_level=int(verification_filter))

    if status_filter == 'active':
        users_queryset = users_queryset.filter(is_active=True)
    elif status_filter == 'inactive':
        users_queryset = users_queryset.filter(is_active=False)
    elif status_filter == 'pending':
        users_queryset = users_queryset.filter(admin_request_status='pending')
    elif status_filter == 'approved':
        users_queryset = users_queryset.filter(admin_request_status='approved')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Username',
        'First Name',
        'Last Name',
        'Email',
        'Phone',
        'Location',
        'Verification Level',
        'Admin Request Status',
        'Account Active',
        'Date Joined',
    ])

    verification_map = dict(CustomUser.VERIFICATION_LEVELS)

    for user in users_queryset:
        writer.writerow([
            user.username,
            user.first_name,
            user.last_name,
            user.email,
            user.phone_number or '',
            user.location or '',
            verification_map.get(user.verification_level, user.verification_level),
            user.admin_request_status,
            'Yes' if user.is_active else 'No',
            user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else '',
        ])

    return response

@user_passes_test(is_admin)
def admin_items(request):
    """Item management page"""
    items = Item.objects.select_related('category', 'steward').all().order_by('-created_at')
    query = (request.GET.get('q') or '').strip()
    category_filter = (request.GET.get('category') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()

    if query:
        items = items.filter(
            models.Q(name__icontains=query)
            | models.Q(description__icontains=query)
            | models.Q(steward__username__icontains=query)
            | models.Q(category__name__icontains=query)
        )

    if category_filter:
        items = items.filter(category_id=category_filter)

    if status_filter in ['available', 'borrowed', 'maintenance', 'retired']:
        items = items.filter(status=status_filter)

    context = {
        'items': items,
        'categories': Category.objects.all().order_by('name'),
        'stewards': CustomUser.objects.filter(is_active=True).order_by('username'),
        'search_query': query,
        'selected_category': category_filter,
        'selected_status': status_filter,
        'total_items': Item.objects.count(),
        'available_items': Item.objects.filter(status='available').count(),
        'borrowed_items': Item.objects.filter(status='borrowed').count(),
        'maintenance_items': Item.objects.filter(status='maintenance').count(),
        'retired_items': Item.objects.filter(status='retired').count(),
    }
    return render(request, 'admin/items.html', context)


@user_passes_test(is_admin)
def admin_item_create(request):
    """Create a new item from admin panel."""
    if request.method != 'POST':
        return redirect('admin_items')

    name = (request.POST.get('name') or '').strip()
    description = (request.POST.get('description') or '').strip()
    location_details = (request.POST.get('location_details') or '').strip()
    category_id = request.POST.get('category')
    new_category_name = (request.POST.get('new_category_name') or '').strip()
    steward_id = request.POST.get('steward')
    condition = request.POST.get('condition', 'good')
    status_value = request.POST.get('status', 'available')

    if not name or not description or not location_details:
        messages.error(request, 'Name, description, and location are required.')
        return redirect('admin_items')

    has_existing_category = bool((category_id or '').strip())
    has_new_category = bool(new_category_name)

    if has_existing_category and has_new_category:
        messages.error(request, 'Choose an existing category or enter a new category, not both.')
        return redirect('admin_items')

    if not has_existing_category and not has_new_category:
        messages.error(request, 'Please select an existing category or enter a new one.')
        return redirect('admin_items')

    category = _create_category_if_needed(category_id, new_category_name)
    if category is None:
        messages.error(request, 'Please select an existing category or enter a new one.')
        return redirect('admin_items')

    steward = CustomUser.objects.filter(id=steward_id, is_active=True).first() if steward_id else request.user
    if steward is None:
        steward = request.user

    primary_image = request.FILES.get('primary_image')
    additional_images = request.FILES.getlist('additional_images')
    image_error = _validate_image_batch(primary_image, additional_images, existing_count=0)
    if image_error:
        messages.error(request, image_error)
        return redirect('admin_items')

    try:
        daily_rate_raw = (request.POST.get('daily_rate') or '').strip()
        deposit_amount_raw = (request.POST.get('deposit_amount') or '').strip()
        tags = (request.POST.get('tags') or '').strip()
        max_borrow_days_raw = (request.POST.get('max_borrow_days') or '').strip()

        if not daily_rate_raw or not deposit_amount_raw or not max_borrow_days_raw:
            messages.error(request, 'Daily rate, deposit amount, and max borrow days are required.')
            return redirect('admin_items')

        max_borrow_days = int(max_borrow_days_raw)

        if max_borrow_days < 1:
            messages.error(request, 'Max borrow days must be at least 1 day.')
            return redirect('admin_items')

        daily_rate = Decimal(daily_rate_raw)
        if daily_rate <= 0:
            messages.error(request, 'Daily rate must be greater than 0.')
            return redirect('admin_items')

        deposit_amount = Decimal(deposit_amount_raw)
        if deposit_amount <= 0:
            messages.error(request, 'Deposit amount must be greater than 0.')
            return redirect('admin_items')

        item = Item.objects.create(
            name=name,
            description=description,
            category=category,
            steward=steward,
            tags=tags,
            condition=condition,
            status=status_value if status_value in ['available', 'borrowed', 'maintenance', 'retired'] else 'available',
            location_details=location_details,
            daily_rate=daily_rate,
            deposit_amount=deposit_amount,
            max_borrow_days=max_borrow_days,
        )

        if primary_image:
            ItemImage.objects.create(item=item, image=primary_image, is_primary=True)

        for image_file in additional_images:
            if image_file:
                ItemImage.objects.create(item=item, image=image_file, is_primary=False)

        messages.success(request, f'Item "{item.name}" created successfully.')
    except InvalidOperation:
        messages.error(request, 'Daily rate and deposit amount must be numeric values.')
    except ValueError:
        messages.error(request, 'Max borrow days must be a whole number.')
    except Exception as exc:
        messages.error(request, f'Failed to create item: {exc}')

    return redirect('admin_items')


@user_passes_test(is_admin)
def admin_item_delete(request, item_id):
    """Delete an item from admin panel."""
    if request.method != 'POST':
        return redirect('admin_items')

    item = get_object_or_404(Item, id=item_id)
    item_name = item.name
    item.delete()
    messages.success(request, f'Item "{item_name}" deleted successfully.')
    return redirect('admin_items')


@user_passes_test(is_admin)
def admin_item_edit(request, item_id):
    """Edit an existing item from admin panel."""
    item = get_object_or_404(Item, id=item_id)

    if request.method == 'GET':
        context = {
            'item': item,
            'categories': Category.objects.all().order_by('name'),
            'stewards': CustomUser.objects.filter(is_active=True).order_by('username'),
        }
        return render(request, 'admin/item_edit.html', context)

    action = (request.POST.get('action') or '').strip()
    if action in ['set_primary_image', 'delete_image']:
        image_id = request.POST.get('image_id')
        image = get_object_or_404(ItemImage, id=image_id, item=item)

        if action == 'set_primary_image':
            if not image.is_primary:
                image.is_primary = True
                image.save()
            messages.success(request, 'Primary image updated.')
            return redirect('admin_item_edit', item_id=item.id)

        if action == 'delete_image':
            total_images = item.images.count()
            if total_images <= 1:
                messages.error(request, 'Cannot delete the last image. Upload a replacement first.')
                return redirect('admin_item_edit', item_id=item.id)

            was_primary = image.is_primary
            image.delete()

            if was_primary:
                fallback_image = item.images.first()
                if fallback_image:
                    fallback_image.is_primary = True
                    fallback_image.save()

            messages.success(request, 'Image deleted successfully.')
            return redirect('admin_item_edit', item_id=item.id)

    name = (request.POST.get('name') or '').strip()
    description = (request.POST.get('description') or '').strip()
    location_details = (request.POST.get('location_details') or '').strip()
    category_id = request.POST.get('category')
    steward_id = request.POST.get('steward')
    condition = request.POST.get('condition', item.condition)
    status_value = request.POST.get('status', item.status)
    tags = (request.POST.get('tags') or '').strip()

    if not name or not description or not location_details or not category_id:
        messages.error(request, 'Name, description, category, and location are required.')
        return redirect('admin_item_edit', item_id=item.id)

    category = get_object_or_404(Category, id=category_id)
    steward = CustomUser.objects.filter(id=steward_id, is_active=True).first() if steward_id else item.steward
    if steward is None:
        steward = item.steward

    try:
        daily_rate_raw = (request.POST.get('daily_rate') or '').strip()
        deposit_amount_raw = (request.POST.get('deposit_amount') or '').strip()
        max_borrow_days = int(request.POST.get('max_borrow_days') or item.max_borrow_days or 14)

        if max_borrow_days < 1:
            messages.error(request, 'Max borrow days must be at least 1 day.')
            return redirect('admin_item_edit', item_id=item.id)

        daily_rate = None
        if daily_rate_raw:
            daily_rate = Decimal(daily_rate_raw)
            if daily_rate < 0:
                messages.error(request, 'Daily rate cannot be negative.')
                return redirect('admin_item_edit', item_id=item.id)

        deposit_amount = None
        if deposit_amount_raw:
            deposit_amount = Decimal(deposit_amount_raw)
            if deposit_amount < 0:
                messages.error(request, 'Deposit amount cannot be negative.')
                return redirect('admin_item_edit', item_id=item.id)

        item.name = name
        item.description = description
        item.category = category
        item.steward = steward
        item.tags = tags
        item.condition = condition if condition in [choice[0] for choice in Item.CONDITION_CHOICES] else item.condition
        item.status = status_value if status_value in [choice[0] for choice in Item.STATUS_CHOICES] else item.status
        item.location_details = location_details
        item.daily_rate = daily_rate
        item.deposit_amount = deposit_amount
        item.max_borrow_days = max_borrow_days
        item.save()

        primary_image = request.FILES.get('primary_image')
        additional_images = request.FILES.getlist('additional_images')
        image_error = _validate_image_batch(primary_image, additional_images, existing_count=item.images.count())
        if image_error:
            messages.error(request, image_error)
            return redirect('admin_item_edit', item_id=item.id)

        if primary_image:
            ItemImage.objects.create(item=item, image=primary_image, is_primary=True)

        for image_file in additional_images:
            if image_file:
                ItemImage.objects.create(item=item, image=image_file, is_primary=False)

        messages.success(request, f'Item "{item.name}" updated successfully.')
        return redirect('admin_items')
    except InvalidOperation:
        messages.error(request, 'Daily rate or deposit amount is invalid. Use numbers only.')
    except ValueError:
        messages.error(request, 'Max borrow days must be a whole number.')
    except Exception as exc:
        messages.error(request, f'Failed to update item: {exc}')

    return redirect('admin_item_edit', item_id=item.id)

@user_passes_test(is_admin)
def admin_bookings(request):
    """Booking management page"""
    bookings_queryset = Booking.objects.select_related('item', 'borrower', 'steward', 'item__steward').all().order_by('-created_at')

    query = (request.GET.get('q') or '').strip()
    status_filter = (request.GET.get('status') or '').strip()
    from_date = (request.GET.get('from_date') or '').strip()
    to_date = (request.GET.get('to_date') or '').strip()

    if query:
        bookings_queryset = bookings_queryset.filter(
            models.Q(booking_id__icontains=query)
            | models.Q(item__name__icontains=query)
            | models.Q(item__location_details__icontains=query)
            | models.Q(borrower__username__icontains=query)
            | models.Q(steward__username__icontains=query)
        )

    valid_statuses = {choice[0] for choice in Booking.STATUS_CHOICES}
    if status_filter in valid_statuses:
        bookings_queryset = bookings_queryset.filter(status=status_filter)

    try:
        if from_date:
            bookings_queryset = bookings_queryset.filter(start_date__gte=datetime.strptime(from_date, '%Y-%m-%d').date())
        if to_date:
            bookings_queryset = bookings_queryset.filter(end_date__lte=datetime.strptime(to_date, '%Y-%m-%d').date())
    except ValueError:
        messages.error(request, 'Invalid date filter provided. Please use valid dates.')

    paginator = Paginator(bookings_queryset, 20)
    page_number = request.GET.get('page')
    bookings = paginator.get_page(page_number)

    booking_ids = [booking.id for booking in bookings.object_list]
    ratings_by_booking = {
        row['booking_id']: row
        for row in Review.objects.filter(booking_id__in=booking_ids)
        .values('booking_id')
        .annotate(avg_rating=models.Avg('rating'), rating_count=models.Count('id'))
    }

    chat_totals_by_booking = {
        row['conversation__related_booking_id']: row['total']
        for row in Message.objects.filter(conversation__related_booking_id__in=booking_ids)
        .values('conversation__related_booking_id')
        .annotate(total=models.Count('id'))
    }
    chat_unread_by_booking = {
        row['conversation__related_booking_id']: row['total']
        for row in Message.objects.filter(
            conversation__related_booking_id__in=booking_ids,
            is_read=False,
        )
        .exclude(sender=request.user)
        .values('conversation__related_booking_id')
        .annotate(total=models.Count('id'))
    }

    for booking in bookings.object_list:
        stats = ratings_by_booking.get(booking.id, {})
        booking.booking_rating_avg = stats.get('avg_rating')
        booking.booking_rating_count = stats.get('rating_count', 0)
        booking.chat_total_count = chat_totals_by_booking.get(booking.id, 0)
        booking.chat_unread_count = chat_unread_by_booking.get(booking.id, 0)

    calendar_bookings = []
    BUFFER_DAYS = 3
    for booking in bookings_queryset.select_related('item'):
        buffer_end = None
        if booking.end_date:
            buffer_end = (booking.end_date + timedelta(days=(BUFFER_DAYS - 1))).isoformat()
        calendar_bookings.append({
            'id': booking.id,
            'booking_id': booking.booking_id,
            'item_name': booking.item.name if booking.item else 'Unknown Item',
            'status': booking.status,
            'status_label': booking.get_status_display(),
            'start_date': booking.start_date.isoformat() if booking.start_date else None,
            'end_date': booking.end_date.isoformat() if booking.end_date else None,
            'buffer_end_date': buffer_end,
        })

    context = {
        'bookings': bookings,
        'search_query': query,
        'selected_status': status_filter,
        'selected_from_date': from_date,
        'selected_to_date': to_date,
        'today': timezone.localdate(),
        'total_bookings': Booking.objects.count(),
        'active_bookings': Booking.objects.filter(status='active').count(),
        'pending_bookings': Booking.objects.filter(status='pending').count(),
        'completed_bookings': Booking.objects.filter(status='completed').count(),
        'overdue_bookings': Booking.objects.filter(status='overdue').count(),
        'cancelled_bookings': Booking.objects.filter(status='cancelled').count(),
        'calendar_bookings': calendar_bookings,
    }
    return render(request, 'admin/bookings.html', context)


@user_passes_test(is_admin)
def admin_suggestions(request):
    """Suggestion management page with search and status filters"""
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'create_item_from_campaign':
            campaign_id = request.POST.get('campaign_id')
            campaign = Campaign.objects.select_related(
                'suggested_item',
                'category',
                'host_organization',
                'created_by',
                'acquired_item',
            ).filter(id=campaign_id).first()

            if not campaign:
                messages.error(request, 'Campaign not found.')
                return redirect('admin_suggestions')

            if campaign.status not in {'funded', 'completed'}:
                messages.error(request, 'Only funded/completed goals can be added as items.')
                return redirect('admin_suggestions')

            try:
                goal_item = campaign.acquired_item
            except Item.DoesNotExist:
                goal_item = None

            if goal_item:
                messages.info(request, f'This goal already has an item: {goal_item.name}.')
                return redirect('admin_item_edit', item_id=goal_item.id)

            if not campaign.suggested_item:
                messages.error(request, 'This campaign has no linked suggestion to create an item from.')
                return redirect('admin_suggestions')

            suggestion = campaign.suggested_item
            selected_category_id = (request.POST.get('category') or '').strip()
            new_category_name = (request.POST.get('new_category_name') or '').strip()
            category = _create_category_if_needed(selected_category_id, new_category_name) or campaign.category or suggestion.category
            if not category:
                messages.error(request, 'Cannot create item without a category. Select or add a category first.')
                return redirect('admin_suggestions')

            location_details = (request.POST.get('location_details') or '').strip()
            if not location_details:
                messages.error(request, 'Pickup location is required before adding this goal as an item.')
                return redirect('admin_suggestions')

            condition_value = (request.POST.get('condition') or 'new').strip()
            valid_conditions = {choice[0] for choice in Item.CONDITION_CHOICES}
            if condition_value not in valid_conditions:
                messages.error(request, 'Invalid item condition selected.')
                return redirect('admin_suggestions')

            try:
                max_borrow_days = int((request.POST.get('max_borrow_days') or '14').strip())
                if max_borrow_days < 1:
                    messages.error(request, 'Max borrow days must be at least 1 day.')
                    return redirect('admin_suggestions')
            except ValueError:
                messages.error(request, 'Max borrow days must be a whole number.')
                return redirect('admin_suggestions')

            try:
                daily_rate_raw = (request.POST.get('daily_rate') or '').strip()
                deposit_amount_raw = (request.POST.get('deposit_amount') or '').strip()

                daily_rate = Decimal(daily_rate_raw) if daily_rate_raw else None
                if daily_rate is not None and daily_rate < 0:
                    messages.error(request, 'Daily rate cannot be negative.')
                    return redirect('admin_suggestions')

                deposit_amount = Decimal(deposit_amount_raw) if deposit_amount_raw else None
                if deposit_amount is not None and deposit_amount < 0:
                    messages.error(request, 'Deposit amount cannot be negative.')
                    return redirect('admin_suggestions')
            except InvalidOperation:
                messages.error(request, 'Daily rate or deposit amount is invalid. Use numbers only.')
                return redirect('admin_suggestions')

            org_steward = None
            if campaign.host_organization_id:
                org_steward = campaign.host_organization.stewards.filter(is_active=True).first()

            selected_steward_id = (request.POST.get('steward') or '').strip()
            selected_steward = CustomUser.objects.filter(id=selected_steward_id, is_active=True).first() if selected_steward_id else None

            steward_user = selected_steward or org_steward or campaign.created_by or request.user
            item_description = suggestion.description or campaign.description or f'Community-funded item from goal: {campaign.title}'

            created_item = Item.objects.create(
                name=suggestion.name,
                description=item_description,
                category=category,
                steward=steward_user,
                host_organization=campaign.host_organization,
                campaign=campaign,
                condition=condition_value,
                status='available',
                location_details=location_details,
                daily_rate=daily_rate,
                deposit_amount=deposit_amount,
                max_borrow_days=max_borrow_days,
            )

            updates = []
            if campaign.category_id != category.id:
                campaign.category = category
                updates.append('category')
            if campaign.status == 'funded':
                campaign.status = 'completed'
                updates.append('status')
            if not campaign.funds_pulled_out:
                campaign.funds_pulled_out = True
                campaign.pulled_out_at = timezone.now()
                campaign.pulled_out_by = request.user
                updates.extend(['funds_pulled_out', 'pulled_out_at', 'pulled_out_by'])
            if updates:
                updates.append('updated_at')
                campaign.save(update_fields=updates)

            if suggestion.category_id != category.id:
                suggestion.category = category
                suggestion.save(update_fields=['category'])

            messages.success(request, f'Created item "{created_item.name}" from goal "{campaign.title}". You can continue editing details below.')
            return redirect('admin_item_edit', item_id=created_item.id)

    queryset = ItemSuggestion.objects.select_related('suggested_by', 'category').exclude(
        campaign__status__in=['funded', 'completed']
    ).all().order_by('-created_at')

    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    if query:
        queryset = queryset.filter(
            models.Q(name__icontains=query) |
            models.Q(description__icontains=query) |
            models.Q(suggested_by__username__icontains=query)
        )

    suggestion_ids = list(queryset.values_list('id', flat=True))
    campaigns_by_suggestion_id = {
        campaign.suggested_item_id: campaign
        for campaign in Campaign.objects.select_related('acquired_item').filter(suggested_item_id__in=suggestion_ids)
    }

    for suggestion in queryset:
        suggestion.goal_campaign = campaigns_by_suggestion_id.get(suggestion.id)

    funded_goal_campaigns = Campaign.objects.select_related(
        'suggested_item',
        'pulled_out_by',
        'acquired_item',
        'host_organization',
    ).filter(
        status__in=['funded', 'completed'],
        suggested_item__isnull=False,
    ).order_by('-funded_date', '-updated_at')

    context = {
        'suggestions': queryset,
        'categories': Category.objects.all().order_by('name'),
        'selected_status': status_filter,
        'search_query': query,
        'total_suggestions': ItemSuggestion.objects.count(),
        'pending_suggestions': ItemSuggestion.objects.filter(status='pending').count(),
        'approved_suggestions': ItemSuggestion.objects.filter(status='approved').count(),
        'rejected_suggestions': ItemSuggestion.objects.filter(status='rejected').count(),
        'campaign_suggestions': ItemSuggestion.objects.filter(status='campaign_created').exclude(
            campaign__status__in=['funded', 'completed']
        ).count(),
        'funded_goal_campaigns': funded_goal_campaigns,
        'pending_pullouts': funded_goal_campaigns.filter(funds_pulled_out=False).count(),
        'completed_pullouts': funded_goal_campaigns.filter(funds_pulled_out=True).count(),
        'stewards': CustomUser.objects.filter(is_active=True).order_by('username'),
        'item_condition_choices': Item.CONDITION_CHOICES,
    }
    return render(request, 'admin/suggestions.html', context)

@user_passes_test(is_admin)
def admin_reports(request):
    """Reports page with real analytics and CSV exports."""

    today = timezone.localdate()
    selected_range = request.GET.get('range', 'month').strip().lower()
    start_param = request.GET.get('start_date', '').strip()
    end_param = request.GET.get('end_date', '').strip()

    if selected_range == 'today':
        start_date = today
        end_date = today
    elif selected_range == 'week':
        start_date = today - timedelta(days=6)
        end_date = today
    elif selected_range == 'quarter':
        start_date = today - timedelta(days=89)
        end_date = today
    elif selected_range == 'year':
        start_date = today - timedelta(days=364)
        end_date = today
    elif selected_range == 'custom':
        try:
            start_date = datetime.strptime(start_param, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_param, '%Y-%m-%d').date()
            if end_date < start_date:
                start_date, end_date = end_date, start_date
        except ValueError:
            selected_range = 'month'
            start_date = today - timedelta(days=29)
            end_date = today
    else:
        selected_range = 'month'
        start_date = today - timedelta(days=29)
        end_date = today

    user_queryset = CustomUser.objects.filter(date_joined__date__range=(start_date, end_date))
    item_queryset = Item.objects.filter(created_at__date__range=(start_date, end_date))
    booking_queryset = Booking.objects.filter(created_at__date__range=(start_date, end_date)).select_related(
        'item',
        'item__category',
        'item__steward',
        'borrower',
        'steward',
    ).prefetch_related('reviews')
    review_queryset = Review.objects.filter(created_at__date__range=(start_date, end_date))
    transaction_queryset = Transaction.objects.filter(created_at__date__range=(start_date, end_date))
    contribution_queryset = Contribution.objects.filter(created_at__date__range=(start_date, end_date))

    unique_borrowers = booking_queryset.values('borrower_id').distinct().count()
    unique_items_borrowed = booking_queryset.values('item_id').distinct().count()

    booking_fee_stats = booking_queryset.exclude(total_fee__isnull=True).aggregate(
        total=models.Sum('total_fee'),
        avg=models.Avg('total_fee'),
    )
    total_booking_fee_amount = booking_fee_stats['total'] or 0
    avg_booking_fee = booking_fee_stats['avg'] or 0

    booking_durations = []
    for start_date_value, end_date_value in booking_queryset.values_list('start_date', 'end_date'):
        if start_date_value and end_date_value and end_date_value >= start_date_value:
            booking_durations.append((end_date_value - start_date_value).days + 1)
    avg_booking_length_days = round(sum(booking_durations) / len(booking_durations), 1) if booking_durations else 0

    average_rating = review_queryset.aggregate(avg=models.Avg('rating'))['avg'] or 0
    total_reviews = review_queryset.count()
    total_completed_transaction_amount = transaction_queryset.filter(status='completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0

    total_users = user_queryset.count()
    total_items = item_queryset.count()
    total_bookings = booking_queryset.count()
    completed_bookings = booking_queryset.filter(status='completed').count()
    active_bookings = booking_queryset.filter(status='active').count()
    cancelled_bookings = booking_queryset.filter(status='cancelled').count()
    pending_bookings = booking_queryset.filter(status='pending').count()
    approved_bookings = booking_queryset.filter(status='approved').count()
    paid_bookings = booking_queryset.filter(status='paid').count()
    declined_bookings = booking_queryset.filter(status='declined').count()
    overdue_bookings = booking_queryset.filter(status='overdue').count()

    top_categories = list(
        Booking.objects.filter(created_at__date__range=(start_date, end_date))
        .values('item__category__name')
        .annotate(total=models.Count('id'))
        .order_by('-total')[:8]
    )
    max_category_total = max((entry['total'] for entry in top_categories), default=0)
    for entry in top_categories:
        entry['pct'] = round((entry['total'] / max_category_total) * 100, 2) if max_category_total else 0

    top_items = list(
        Booking.objects.filter(created_at__date__range=(start_date, end_date))
        .values('item__name')
        .annotate(total=models.Count('id'))
        .order_by('-total')[:8]
    )

    top_borrowers = list(
        booking_queryset.values('borrower__username')
        .annotate(total=models.Count('id'), total_fee=models.Sum('total_fee'))
        .order_by('-total')[:8]
    )
    max_borrower_total = max((entry['total'] for entry in top_borrowers), default=0)
    for entry in top_borrowers:
        entry['pct'] = round((entry['total'] / max_borrower_total) * 100, 2) if max_borrower_total else 0
        entry['total_fee'] = entry['total_fee'] or 0

    top_stewards = list(
        booking_queryset.values('item__steward__username')
        .annotate(total=models.Count('id'), total_fee=models.Sum('total_fee'))
        .order_by('-total')[:8]
    )
    max_steward_total = max((entry['total'] for entry in top_stewards), default=0)
    for entry in top_stewards:
        entry['pct'] = round((entry['total'] / max_steward_total) * 100, 2) if max_steward_total else 0
        entry['total_fee'] = entry['total_fee'] or 0

    booking_status_rows = [
        {'label': 'Pending', 'count': pending_bookings},
        {'label': 'Approved', 'count': approved_bookings},
        {'label': 'Paid', 'count': paid_bookings},
        {'label': 'Active', 'count': active_bookings},
        {'label': 'Completed', 'count': completed_bookings},
        {'label': 'Cancelled', 'count': cancelled_bookings},
        {'label': 'Overdue', 'count': overdue_bookings},
        {'label': 'Declined', 'count': declined_bookings},
    ]
    max_status_total = max((row['count'] for row in booking_status_rows), default=0)
    for row in booking_status_rows:
        row['pct'] = round((row['count'] / max_status_total) * 100, 2) if max_status_total else 0

    payment_method_rows = list(
        transaction_queryset.values('payment_method')
        .annotate(total=models.Count('id'), amount=models.Sum('amount'))
        .order_by('-total')
    )
    max_payment_method_total = max((row['total'] for row in payment_method_rows), default=0)
    for row in payment_method_rows:
        row['label'] = row['payment_method'].replace('_', ' ').title()
        row['amount'] = row['amount'] or 0
        row['pct'] = round((row['total'] / max_payment_method_total) * 100, 2) if max_payment_method_total else 0

    completion_rate = round((completed_bookings / total_bookings) * 100, 1) if total_bookings else 0
    approval_rate = round((approved_bookings / total_bookings) * 100, 1) if total_bookings else 0
    overdue_rate = round((overdue_bookings / total_bookings) * 100, 1) if total_bookings else 0

    best_steward_name = ''
    best_steward_fee = 0
    if top_stewards:
        best_steward = top_stewards[0]
        best_steward_name = best_steward.get('item__steward__username', 'N/A')
        best_steward_fee = best_steward.get('total_fee', 0) or 0

    top_category_name = 'Uncategorized'
    top_category_total = 0
    if top_categories:
        top_category_name = top_categories[0].get('item__category__name', 'Uncategorized') or 'Uncategorized'
        top_category_total = top_categories[0].get('total', 0) or 0

    most_borrowed_item_name = 'N/A'
    most_borrowed_item_total = 0
    if top_items:
        most_borrowed_item_name = top_items[0].get('item__name', 'N/A') or 'N/A'
        most_borrowed_item_total = top_items[0].get('total', 0) or 0

    top_borrower_name = 'N/A'
    top_borrower_total = 0
    top_borrower_fee = 0
    if top_borrowers:
        top_borrower_name = top_borrowers[0].get('borrower__username', 'N/A') or 'N/A'
        top_borrower_total = top_borrowers[0].get('total', 0) or 0
        top_borrower_fee = top_borrowers[0].get('total_fee', 0) or 0

    export_type = request.GET.get('export', '').strip().lower()
    if export_type in {'users', 'items', 'bookings', 'contributions', 'full'}:
        response = HttpResponse(content_type='text/csv')
        filename_suffix = f"{start_date.isoformat()}_to_{end_date.isoformat()}"
        response['Content-Disposition'] = f'attachment; filename="knot_{export_type}_report_{filename_suffix}.csv"'
        writer = csv.writer(response)

        if export_type == 'users':
            writer.writerow(['username', 'first_name', 'last_name', 'email', 'phone_number', 'bio', 'location', 'joined_at', 'verification_level', 'email_verified', 'phone_verified', 'id_verified', 'is_active', 'is_admin_approved', 'total_bookings_made', 'total_amount_paid', 'avg_rating', 'steward_status'])
            for user in user_queryset.order_by('-date_joined'):
                user_bookings = Booking.objects.filter(borrower=user).aggregate(
                    total=models.Count('id'),
                    total_fee=models.Sum('total_fee')
                )
                total_bookings = user_bookings['total'] or 0
                total_paid = user_bookings['total_fee'] or 0
                steward_status = 'Yes' if Item.objects.filter(steward=user).exists() else 'No'

                writer.writerow([
                    user.username,
                    user.first_name or '',
                    user.last_name or '',
                    user.email,
                    getattr(user, 'phone_number', '') or '',
                    getattr(user, 'bio', '') or '',
                    getattr(user, 'location', '') or '',
                    user.date_joined.isoformat(),
                    getattr(user, 'verification_level', 0),
                    'Yes' if getattr(user, 'email_verified', False) else 'No',
                    'Yes' if getattr(user, 'phone_verified', False) else 'No',
                    'Yes' if getattr(user, 'id_verified', False) else 'No',
                    'Yes' if user.is_active else 'No',
                    'Yes' if getattr(user, 'is_admin_approved', False) else 'No',
                    total_bookings,
                    round(float(total_paid), 2),
                    round(float(getattr(user, 'average_rating', 0) or 0), 2),
                    steward_status,
                ])
            return response

        if export_type == 'items':
            writer.writerow(['name', 'slug', 'category', 'status', 'condition', 'steward', 'location_details', 'daily_rate', 'deposit_amount', 'max_borrow_days', 'total_bookings', 'description', 'created_at', 'updated_at'])
            for item in item_queryset.select_related('category', 'steward').order_by('-created_at'):
                writer.writerow([
                    item.name,
                    item.slug,
                    item.category.name if item.category else '',
                    item.status,
                    item.condition,
                    item.steward.username if item.steward else '',
                    item.location_details or '',
                    item.daily_rate or '',
                    item.deposit_amount or '',
                    item.max_borrow_days,
                    item.total_bookings,
                    item.description or '',
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ])
            return response

        if export_type == 'bookings':
            writer.writerow(['booking_id', 'item', 'item_category', 'steward', 'borrower', 'status', 'start_date', 'end_date', 'return_delayed', 'item_rating', 'steward_rating', 'total_fee', 'booking_duration_days', 'created_at'])
            for booking in booking_queryset.order_by('-created_at'):
                return_delayed = 'Yes' if ((booking.returned_at and booking.end_date and booking.returned_at.date() > booking.end_date) or booking.status == 'overdue') else 'No'
                borrower_review = next((review for review in booking.reviews.all() if review.review_type == 'borrower_to_steward'), None)
                steward_review = next((review for review in booking.reviews.all() if review.review_type == 'steward_to_borrower'), None)
                item_rating = borrower_review.item_condition_rating if borrower_review and borrower_review.item_condition_rating is not None else (borrower_review.rating if borrower_review else '')
                steward_rating = borrower_review.rating if borrower_review and borrower_review.rating is not None else (steward_review.rating if steward_review else '')
                duration = (booking.end_date - booking.start_date).days + 1 if booking.start_date and booking.end_date else 0

                writer.writerow([
                    booking.booking_id,
                    booking.item.name if booking.item else '',
                    booking.item.category.name if booking.item and booking.item.category else '',
                    booking.item.steward.username if booking.item and booking.item.steward else '',
                    booking.borrower.username if booking.borrower else '',
                    booking.status,
                    booking.start_date,
                    booking.end_date,
                    return_delayed,
                    item_rating,
                    steward_rating,
                    booking.total_fee or 0,
                    duration,
                    booking.created_at.isoformat(),
                ])
            return response

        if export_type == 'contributions':
            writer.writerow(['contributor', 'goal_title', 'amount', 'status', 'contributed_at'])
            for contribution in contribution_queryset.select_related('user', 'campaign', 'transaction').order_by('-created_at'):
                writer.writerow([
                    contribution.user.username if contribution.user else 'Anonymous',
                    contribution.campaign.title if contribution.campaign else '',
                    float(contribution.amount),
                    contribution.transaction.status if contribution.transaction else 'unknown',
                    contribution.created_at.isoformat(),
                ])
            return response

        # Full detailed report
        writer.writerow(['KNOT FULL DETAILED REPORT', f'{start_date.isoformat()} to {end_date.isoformat()}'])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['=== SUMMARY METRICS ==='])
        writer.writerow(['new_users', user_queryset.count()])
        writer.writerow(['new_items', item_queryset.count()])
        writer.writerow(['total_bookings', booking_queryset.count()])
        writer.writerow(['completed_bookings', booking_queryset.filter(status='completed').count()])
        writer.writerow(['active_bookings', booking_queryset.filter(status='active').count()])
        writer.writerow(['overdue_bookings', booking_queryset.filter(status='overdue').count()])
        writer.writerow(['unique_borrowers', unique_borrowers])
        writer.writerow(['avg_booking_duration_days', avg_booking_length_days])
        writer.writerow(['completion_rate_%', completion_rate])
        writer.writerow(['overdue_rate_%', overdue_rate])
        writer.writerow([])  
        
        # Financial metrics
        writer.writerow(['=== FINANCIAL METRICS ==='])
        writer.writerow(['total_booking_fees', total_booking_fee_amount])
        writer.writerow(['avg_booking_fee', avg_booking_fee])
        writer.writerow(['total_completed_transaction_amount', total_completed_transaction_amount])
        writer.writerow([])  
        
        # Rating metrics
        writer.writerow(['=== RATING & REVIEW METRICS ==='])
        writer.writerow(['total_reviews', total_reviews])
        writer.writerow(['average_rating', average_rating])
        writer.writerow([])  
        
        # Top performers
        writer.writerow(['=== TOP PERFORMERS ==='])
        writer.writerow(['top_borrower', top_borrower_name])
        writer.writerow(['top_borrower_bookings', top_borrower_total])
        writer.writerow(['top_borrower_fees', top_borrower_fee])
        writer.writerow([])  
        writer.writerow(['top_steward', best_steward_name])
        writer.writerow(['top_steward_bookings', max_steward_total])
        writer.writerow(['top_steward_fees', best_steward_fee])
        writer.writerow([])  
        
        # Most popular items/categories
        writer.writerow(['=== POPULAR ITEMS & CATEGORIES ==='])
        writer.writerow(['top_category', top_category_name])
        writer.writerow(['top_category_bookings', top_category_total])
        writer.writerow([])  
        writer.writerow(['most_borrowed_item', most_borrowed_item_name])
        writer.writerow(['most_borrowed_item_count', most_borrowed_item_total])
        writer.writerow([])  
        
        # Booking status breakdown
        writer.writerow(['=== BOOKING STATUS BREAKDOWN ==='])
        for row in booking_status_rows:
            writer.writerow([row['label'], row['count']])
        writer.writerow([])  
        
        # Top items detail
        writer.writerow(['=== TOP 10 ITEMS ==='])
        writer.writerow(['item_name', 'booking_count'])
        for item_row in top_items[:10]:
            writer.writerow([item_row.get('item__name', ''), item_row.get('total', 0)])
        writer.writerow([])  
        
        # Top borrowers detail
        writer.writerow(['=== TOP 10 BORROWERS ==='])
        writer.writerow(['borrower_username', 'bookings_made', 'total_fees_paid'])
        for borrower_row in top_borrowers[:10]:
            writer.writerow([borrower_row.get('borrower__username', ''), borrower_row.get('total', 0), borrower_row.get('total_fee', 0) or 0])
        writer.writerow([])  
        
        # Top stewards detail
        writer.writerow(['=== TOP 10 STEWARDS ==='])
        writer.writerow(['steward_username', 'items_borrowed', 'total_fees_generated'])
        for steward_row in top_stewards[:10]:
            writer.writerow([steward_row.get('item__steward__username', ''), steward_row.get('total', 0), steward_row.get('total_fee', 0) or 0])
        writer.writerow([])  
        
        # Categories breakdown
        writer.writerow(['=== CATEGORY BREAKDOWN ==='])
        writer.writerow(['category_name', 'booking_count'])
        for cat_row in top_categories[:15]:
            writer.writerow([cat_row.get('item__category__name', 'Uncategorized'), cat_row.get('total', 0)])
        
        return response

    total_users = user_queryset.count()
    total_items = item_queryset.count()
    total_bookings = booking_queryset.count()
    completed_bookings = booking_queryset.filter(status='completed').count()
    active_bookings = booking_queryset.filter(status='active').count()
    cancelled_bookings = booking_queryset.filter(status='cancelled').count()
    pending_bookings = booking_queryset.filter(status='pending').count()
    approved_bookings = booking_queryset.filter(status='approved').count()
    paid_bookings = booking_queryset.filter(status='paid').count()
    declined_bookings = booking_queryset.filter(status='declined').count()
    overdue_bookings = booking_queryset.filter(status='overdue').count()

    unique_borrowers = booking_queryset.values('borrower_id').distinct().count()
    unique_items_borrowed = booking_queryset.values('item_id').distinct().count()

    booking_fee_stats = booking_queryset.exclude(total_fee__isnull=True).aggregate(
        total=models.Sum('total_fee'),
        avg=models.Avg('total_fee'),
    )
    total_booking_fee_amount = booking_fee_stats['total'] or 0
    avg_booking_fee = booking_fee_stats['avg'] or 0

    booking_durations = []
    for start_date_value, end_date_value in booking_queryset.values_list('start_date', 'end_date'):
        if start_date_value and end_date_value and end_date_value >= start_date_value:
            booking_durations.append((end_date_value - start_date_value).days + 1)
    avg_booking_length_days = round(sum(booking_durations) / len(booking_durations), 1) if booking_durations else 0

    average_rating = review_queryset.aggregate(avg=models.Avg('rating'))['avg'] or 0
    total_reviews = review_queryset.count()
    total_completed_transaction_amount = transaction_queryset.filter(status='completed').aggregate(
        total=models.Sum('amount')
    )['total'] or 0

    # Build date sequence over selected range for trend charts.
    date_sequence = []
    cursor = start_date
    while cursor <= end_date:
        date_sequence.append(cursor)
        cursor += timedelta(days=1)

    joined_by_day = {
        row['day']: row['total']
        for row in user_queryset.annotate(day=TruncDate('date_joined')).values('day').annotate(total=models.Count('id'))
    }
    bookings_by_day = {
        row['day']: row['total']
        for row in booking_queryset.annotate(day=TruncDate('created_at')).values('day').annotate(total=models.Count('id'))
    }

    user_growth_series = [
        {
            'label': day.strftime('%b %d'),
            'count': joined_by_day.get(day, 0),
        }
        for day in date_sequence
    ]
    max_user_growth = max((point['count'] for point in user_growth_series), default=0)
    for point in user_growth_series:
        point['pct'] = round((point['count'] / max_user_growth) * 100, 2) if max_user_growth else 0

    booking_volume_series = [
        {
            'label': day.strftime('%b %d'),
            'count': bookings_by_day.get(day, 0),
        }
        for day in date_sequence
    ]
    max_booking_volume = max((point['count'] for point in booking_volume_series), default=0)
    for point in booking_volume_series:
        point['pct'] = round((point['count'] / max_booking_volume) * 100, 2) if max_booking_volume else 0

    top_categories = list(
        Booking.objects.filter(created_at__date__range=(start_date, end_date))
        .values('item__category__name')
        .annotate(total=models.Count('id'))
        .order_by('-total')[:8]
    )
    max_category_total = max((entry['total'] for entry in top_categories), default=0)
    for entry in top_categories:
        entry['pct'] = round((entry['total'] / max_category_total) * 100, 2) if max_category_total else 0

    top_items = list(
        Booking.objects.filter(created_at__date__range=(start_date, end_date))
        .values('item__name')
        .annotate(total=models.Count('id'))
        .order_by('-total')[:8]
    )

    top_borrowers = list(
        booking_queryset.values('borrower__username')
        .annotate(total=models.Count('id'), total_fee=models.Sum('total_fee'))
        .order_by('-total')[:8]
    )
    max_borrower_total = max((entry['total'] for entry in top_borrowers), default=0)
    for entry in top_borrowers:
        entry['pct'] = round((entry['total'] / max_borrower_total) * 100, 2) if max_borrower_total else 0
        entry['total_fee'] = entry['total_fee'] or 0

    top_stewards = list(
        booking_queryset.values('item__steward__username')
        .annotate(total=models.Count('id'), total_fee=models.Sum('total_fee'))
        .order_by('-total')[:8]
    )
    max_steward_total = max((entry['total'] for entry in top_stewards), default=0)
    for entry in top_stewards:
        entry['pct'] = round((entry['total'] / max_steward_total) * 100, 2) if max_steward_total else 0
        entry['total_fee'] = entry['total_fee'] or 0

    booking_status_rows = [
        {'label': 'Pending', 'count': pending_bookings},
        {'label': 'Approved', 'count': approved_bookings},
        {'label': 'Paid', 'count': paid_bookings},
        {'label': 'Active', 'count': active_bookings},
        {'label': 'Completed', 'count': completed_bookings},
        {'label': 'Cancelled', 'count': cancelled_bookings},
        {'label': 'Overdue', 'count': overdue_bookings},
        {'label': 'Declined', 'count': declined_bookings},
    ]
    max_status_total = max((row['count'] for row in booking_status_rows), default=0)
    for row in booking_status_rows:
        row['pct'] = round((row['count'] / max_status_total) * 100, 2) if max_status_total else 0

    transaction_status_rows = list(
        transaction_queryset.values('status')
        .annotate(total=models.Count('id'), amount=models.Sum('amount'))
        .order_by('-total')
    )
    max_transaction_status_total = max((row['total'] for row in transaction_status_rows), default=0)
    for row in transaction_status_rows:
        row['label'] = row['status'].replace('_', ' ').title()
        row['amount'] = row['amount'] or 0
        row['pct'] = round((row['total'] / max_transaction_status_total) * 100, 2) if max_transaction_status_total else 0

    payment_method_rows = list(
        transaction_queryset.values('payment_method')
        .annotate(total=models.Count('id'), amount=models.Sum('amount'))
        .order_by('-total')
    )
    max_payment_method_total = max((row['total'] for row in payment_method_rows), default=0)
    for row in payment_method_rows:
        row['label'] = row['payment_method'].replace('_', ' ').title()
        row['amount'] = row['amount'] or 0
        row['pct'] = round((row['total'] / max_payment_method_total) * 100, 2) if max_payment_method_total else 0

    rating_count_map = {
        int(row['rating']): row['total']
        for row in review_queryset.values('rating').annotate(total=models.Count('id'))
        if row['rating'] is not None
    }
    review_rating_rows = []
    for stars in range(5, 0, -1):
        review_rating_rows.append({'label': f'{stars} Stars', 'count': rating_count_map.get(stars, 0)})
    max_review_rating_total = max((row['count'] for row in review_rating_rows), default=0)
    for row in review_rating_rows:
        row['pct'] = round((row['count'] / max_review_rating_total) * 100, 2) if max_review_rating_total else 0

    completion_rate = round((completed_bookings / total_bookings) * 100, 1) if total_bookings else 0
    approval_rate = round((approved_bookings / total_bookings) * 100, 1) if total_bookings else 0
    overdue_rate = round((overdue_bookings / total_bookings) * 100, 1) if total_bookings else 0

    # Calculate previous period metrics for comparison
    period_duration = (end_date - start_date).days + 1
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=period_duration - 1)
    
    prev_booking_queryset = Booking.objects.filter(
        created_at__date__range=(prev_start_date, prev_end_date)
    )
    prev_total_bookings = prev_booking_queryset.count()
    prev_completed_bookings = prev_booking_queryset.filter(status='completed').count()
    prev_overdue_bookings = prev_booking_queryset.filter(status='overdue').count()
    
    # Calculate trends
    bookings_trend = 0
    bookings_direction = 'neutral'
    if prev_total_bookings > 0:
        bookings_trend = round(((total_bookings - prev_total_bookings) / prev_total_bookings) * 100, 1)
        bookings_direction = 'up' if bookings_trend > 0 else ('down' if bookings_trend < 0 else 'neutral')
    
    completion_trend = 0
    completion_direction = 'neutral'
    prev_completion_rate = round((prev_completed_bookings / prev_total_bookings) * 100, 1) if prev_total_bookings else 0
    if prev_completion_rate > 0:
        completion_trend = round(completion_rate - prev_completion_rate, 1)
        completion_direction = 'up' if completion_trend > 0 else ('down' if completion_trend < 0 else 'neutral')
    
    # Get best steward and highest risk
    context = {
        'selected_range': selected_range,
        'start_date': start_date,
        'end_date': end_date,
        'total_users': total_users,
        'total_items': total_items,
        'total_bookings': total_bookings,
        'completed_bookings': completed_bookings,
        'active_bookings': active_bookings,
        'cancelled_bookings': cancelled_bookings,
        'pending_bookings': pending_bookings,
        'approved_bookings': approved_bookings,
        'paid_bookings': paid_bookings,
        'declined_bookings': declined_bookings,
        'overdue_bookings': overdue_bookings,
        'unique_borrowers': unique_borrowers,
        'unique_items_borrowed': unique_items_borrowed,
        'avg_booking_length_days': avg_booking_length_days,
        'avg_booking_fee': round(float(avg_booking_fee), 2) if avg_booking_fee else 0,
        'total_booking_fee_amount': total_booking_fee_amount,
        'total_reviews': total_reviews,
        'average_rating': round(float(average_rating), 2),
        'total_completed_transaction_amount': total_completed_transaction_amount,
        'completion_rate': completion_rate,
        'approval_rate': approval_rate,
        'overdue_rate': overdue_rate,
        'bookings_trend': bookings_trend,
        'bookings_direction': bookings_direction,
        'completion_trend': completion_trend,
        'completion_direction': completion_direction,
        'best_steward_name': best_steward_name,
        'best_steward_fee': best_steward_fee,
        'top_category_name': top_category_name,
        'top_category_total': top_category_total,
        'most_borrowed_item_name': most_borrowed_item_name,
        'most_borrowed_item_total': most_borrowed_item_total,
        'top_borrower_name': top_borrower_name,
        'top_borrower_total': top_borrower_total,
        'top_borrower_fee': top_borrower_fee,
        'user_growth_series': user_growth_series,
        'max_user_growth': max_user_growth,
        'booking_volume_series': booking_volume_series,
        'max_booking_volume': max_booking_volume,
        'top_categories': top_categories,
        'max_category_total': max_category_total,
        'top_items': top_items,
        'top_borrowers': top_borrowers,
        'max_borrower_total': max_borrower_total,
        'top_stewards': top_stewards,
        'max_steward_total': max_steward_total,
        'booking_status_rows': booking_status_rows,
        'max_status_total': max_status_total,
        'transaction_status_rows': transaction_status_rows,
        'max_transaction_status_total': max_transaction_status_total,
        'payment_method_rows': payment_method_rows,
        'max_payment_method_total': max_payment_method_total,
        'review_rating_rows': review_rating_rows,
        'max_review_rating_total': max_review_rating_total,
        'total_contributions': contribution_queryset.count(),
    }
    return render(request, 'admin/reports.html', context)

@user_passes_test(is_admin)
def admin_settings(request):
    """Settings page"""
    site = Site.objects.get_current(request)
    site_settings, _ = SiteSettings.objects.get_or_create(site=site)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'general':
            site_settings.site_name = request.POST.get('site_name', site_settings.site_name).strip() or site_settings.site_name
            site_settings.tagline = request.POST.get('tagline', site_settings.tagline).strip() or site_settings.tagline
            site.save(update_fields=['name'])
            site_settings.save(update_fields=['site_name', 'tagline'])
            messages.success(request, 'General settings saved successfully.')

        elif action == 'email':
            site_settings.contact_email = request.POST.get('contact_email', site_settings.contact_email).strip()
            site_settings.support_email = request.POST.get('support_email', site_settings.support_email).strip()
            site_settings.save(update_fields=['contact_email', 'support_email'])
            messages.success(request, 'Email settings saved successfully.')

        elif action == 'security':
            site_settings.maintenance_mode = request.POST.get('maintenance_mode') == 'on'
            site_settings.maintenance_message = request.POST.get('maintenance_message', site_settings.maintenance_message).strip()
            site_settings.save(update_fields=['maintenance_mode', 'maintenance_message'])
            messages.success(request, 'Security settings saved successfully.')

        elif action == 'payments':
            site_settings.enable_payments = request.POST.get('enable_payments') == 'on'
            site_settings.save(update_fields=['enable_payments'])
            messages.success(request, 'Payment settings saved successfully.')

        elif action == 'notifications':
            site_settings.enable_messaging = request.POST.get('enable_messaging') == 'on'
            site_settings.save(update_fields=['enable_messaging'])
            messages.success(request, 'Notification settings saved successfully.')

        site_settings.update_statistics()
        return redirect('admin_settings')

    context = {
        'site_settings': site_settings,
        'site_domain': site.domain,
        'total_users': CustomUser.objects.count(),
        'total_items': Item.objects.filter(status__in=['available', 'borrowed', 'maintenance']).count(),
        'total_bookings': Booking.objects.count(),
        'active_bookings': Booking.objects.filter(status__in=['approved', 'paid', 'active']).count(),
        'overdue_bookings': Booking.objects.filter(status='overdue').count(),
        'total_transactions': Transaction.objects.count(),
        'completed_transactions': Transaction.objects.filter(status='completed').count(),
        'total_contributions': Contribution.objects.aggregate(total=models.Sum('amount'))['total'] or 0,
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
        'recent_notifications': list(Notification.objects.select_related('user').order_by('-created_at')[:6]),
        'recent_audit_entries': list(BookingHistory.objects.select_related('booking', 'performed_by').order_by('-timestamp')[:8]),
        'email_host': getattr(settings, 'EMAIL_HOST', 'Not configured'),
        'email_port': getattr(settings, 'EMAIL_PORT', 'Not configured'),
        'email_user': getattr(settings, 'EMAIL_HOST_USER', 'Not configured'),
        'email_from': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not configured'),
        'email_password_masked': '********' if getattr(settings, 'EMAIL_HOST_PASSWORD', '') else 'Not configured',
        'session_timeout_minutes': int(getattr(settings, 'SESSION_COOKIE_AGE', 1800) / 60),
        'maintenance_mode': site_settings.maintenance_mode,
        'payhero_username': getattr(settings, 'PAYHERO_USERNAME', 'Not configured'),
        'payhero_channel_id': getattr(settings, 'PAYHERO_CHANNEL_ID', 'Not configured'),
        'payhero_base_url': getattr(settings, 'PAYHERO_BASE_URL', 'Not configured'),
        'payhero_callback_url': getattr(settings, 'PAYHERO_CALLBACK_URL', 'Not configured'),
        'payhero_booking_callback_url': getattr(settings, 'BOOKING_PAYHERO_CALLBACK_URL', 'Not configured'),
        'payhero_masked_key': f"{getattr(settings, 'PAYHERO_API_KEY', '')[:4]}...{getattr(settings, 'PAYHERO_API_KEY', '')[-4:]}" if getattr(settings, 'PAYHERO_API_KEY', '') else 'Not configured',
        'site_url': getattr(settings, 'SITE_URL', request.build_absolute_uri('/')),
        'payhero_test_mode': getattr(settings, 'PAYHERO_TEST_MODE', False),
    }
    return render(request, 'admin/settings.html', context)

# ======================
# ADMIN ACTION VIEWS
# ======================

@user_passes_test(is_admin)
def admin_user_activate(request, user_id):
    """Activate a user account"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        user.is_active = True
        user.save()
        messages.success(request, f'User {user.username} has been activated.')
    return redirect('admin_users')

@user_passes_test(is_admin)
def admin_user_deactivate(request, user_id):
    """Deactivate a user account"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        user.is_active = False
        user.save()
        messages.success(request, f'User {user.username} has been deactivated.')
    return redirect('admin_users')

@user_passes_test(is_admin)
def admin_user_delete(request, user_id):
    """Delete a user account"""
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        username = user.username
        user.delete()
        messages.success(request, f'User {username} has been deleted.')
    return redirect('admin_users')

@user_passes_test(is_admin)
def admin_item_update_status(request, item_id):
    """Update item status"""
    if request.method == 'POST':
        from apps.items.models import Item
        item = get_object_or_404(Item, id=item_id)
        new_status = request.POST.get('status')
        if new_status in ['available', 'borrowed', 'maintenance', 'retired']:
            item.status = new_status
            item.save()
            messages.success(request, f'Item "{item.name}" status updated to {item.get_status_display()}.')
    return redirect('admin_items')

@user_passes_test(is_admin)
def admin_booking_approve(request, booking_id):
    """Approve a booking and set pickup details"""
    if request.method == 'POST':
        from apps.bookings.models import Booking
        booking = get_object_or_404(Booking, id=booking_id)
        
        if booking.status != 'pending':
            messages.error(request, f'Cannot approve booking with status {booking.status}')
            return redirect('admin_bookings')

        if not booking.borrower_id_photo:
            messages.error(request, 'Cannot approve this booking because the borrower has not submitted an ID photo.')
            return redirect('admin_booking_review', booking_id=booking.id)
        
        # Update booking with approval details
        booking.status = 'approved'
        booking.steward = request.user
        booking.approved_at = timezone.now()
        
        # Set pickup details from form
        pickup_date = request.POST.get('pickup_date')
        pickup_time = request.POST.get('pickup_time')
        pickup_location = request.POST.get('pickup_location', booking.item.location_details)
        notes = request.POST.get('notes', '')

        if pickup_date:
            try:
                pickup_date_obj = datetime.strptime(pickup_date, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid pickup date format. Please use a valid date.')
                return redirect('admin_booking_review', booking_id=booking.id)

            today = timezone.localdate()
            if pickup_date_obj < today:
                messages.error(request, 'Pickup date cannot be in the past.')
                return redirect('admin_booking_review', booking_id=booking.id)

            if pickup_date_obj > booking.start_date:
                messages.error(
                    request,
                    f'Pickup date cannot be after the member\'s requested start date ({booking.start_date:%b %d, %Y}).'
                )
                return redirect('admin_booking_review', booking_id=booking.id)
        
        if pickup_date:
            booking.pickup_date = pickup_date
        if pickup_time:
            booking.pickup_time = pickup_time
        booking.pickup_location = pickup_location
        booking.notes = notes

        if not booking.total_fee:
            days = (booking.end_date - booking.start_date).days + 1
            daily_rate = booking.item.daily_rate or 0
            booking.total_fee = daily_rate * days
        
        booking.save()

        Notification.objects.create(
            user=booking.borrower,
            notification_type='booking_approved',
            title='Booking Approved',
            message=f'Your booking for {booking.item.name} has been approved. Please complete payment before pickup.',
            related_url='/dashboard/'
        )
        messages.success(request, f'Booking for "{booking.item.name}" has been approved with pickup details.')
    return redirect('admin_bookings')

@user_passes_test(is_admin)
def admin_booking_reject(request, booking_id):
    """Reject a booking"""
    if request.method == 'POST':
        from apps.bookings.models import Booking
        booking = get_object_or_404(Booking, id=booking_id)
        booking.status = 'declined'
        rejection_note = request.POST.get('notes', '')
        if rejection_note:
            booking.notes = rejection_note
        booking.save()

        Notification.objects.create(
            user=booking.borrower,
            notification_type='booking_declined',
            title='Booking Declined',
            message=f'Your booking for {booking.item.name} was declined.{(" Note: " + rejection_note) if rejection_note else ""}',
            related_url='/dashboard/'
        )
        messages.success(request, f'Booking for "{booking.item.name}" has been rejected.')
    return redirect('admin_bookings')


@user_passes_test(is_admin)
def admin_booking_review(request, booking_id):
    """Detailed booking review page for approve/decline workflow"""
    booking = get_object_or_404(Booking, id=booking_id)
    booking_reviews = Review.objects.filter(
        booking=booking,
    ).select_related('reviewer', 'reviewee').order_by('-created_at')

    item_reviews = Review.objects.filter(
        booking__item=booking.item,
        review_type='borrower_to_steward',
    ).select_related('reviewer').order_by('-created_at')[:20]

    booking_chat_messages = Message.objects.filter(
        conversation__related_booking=booking,
    ).select_related('sender').order_by('created_at')[:120]

    item_rating_avg = item_reviews.aggregate(avg=models.Avg('rating'))['avg'] or 0

    return render(request, 'admin/booking_approval.html', {
        'booking': booking,
        'today': timezone.localdate(),
        'booking_reviews': booking_reviews,
        'item_reviews': item_reviews,
        'booking_chat_messages': booking_chat_messages,
        'item_rating_avg': round(float(item_rating_avg), 2),
    })

@user_passes_test(is_admin)
def admin_booking_return(request, booking_id):
    """Mark booking as returned"""
    if request.method == 'POST':
        from apps.bookings.models import Booking, BookingHistory
        from apps.core.models import Notification
        
        booking = get_object_or_404(Booking, id=booking_id)

        if booking.status in ['active', 'overdue']:
            # check_in keeps booking and item status in sync.
            booking.check_in()
        else:
            booking.status = 'completed'
            booking.returned_at = timezone.now()
            booking.save()

            # Fallback: ensure item is re-listed for future bookings.
            booking.item.status = 'available'
            booking.item.save()

        BookingHistory.objects.create(
            booking=booking,
            action='returned',
            performed_by=request.user,
            notes='Marked returned from admin bookings page.',
        )
        
        # Send notification to borrower to rate the item
        Notification.objects.create(
            user=booking.borrower,
            notification_type='booking_completed',
            title='Item Returned - Please Rate It',
            message=(
                f'Thank you for returning {booking.item.name}! '
                f'Please rate the item and the steward to help the community.'
            ),
            related_url='/dashboard/',
        )
        
        messages.success(request, f'Booking for "{booking.item.name}" has been marked as returned.')
    return redirect('admin_bookings')


@user_passes_test(is_admin)
def admin_booking_checkout(request, booking_id):
    """Mark a paid booking as checked out to the borrower."""
    if request.method == 'POST':
        from apps.bookings.models import Booking, BookingHistory

        booking = get_object_or_404(Booking, id=booking_id)

        if booking.status != 'paid':
            messages.error(request, f'Cannot check out booking with status {booking.status}.')
            return redirect('admin_bookings')

        booking.check_out()

        BookingHistory.objects.create(
            booking=booking,
            action='checked_out',
            performed_by=request.user,
            notes='Checked out by admin/steward from admin bookings page.',
        )

        Notification.objects.create(
            user=booking.borrower,
            notification_type='booking_reminder',
            title='Booking Checked Out',
            message=(
                f'Your booking for {booking.item.name} has been checked out. '
                f'Please return it by {booking.end_date:%b %d, %Y}.'
            ),
            related_url='/dashboard/',
        )

        messages.success(request, f'Booking for "{booking.item.name}" is now active.')

    return redirect('admin_bookings')


@user_passes_test(is_admin)
def admin_booking_mark_overdue(request, booking_id):
    """Flag an active booking as overdue and notify the borrower."""
    if request.method == 'POST':
        from apps.bookings.models import Booking, BookingHistory

        booking = get_object_or_404(Booking, id=booking_id)

        if booking.status not in ['active', 'overdue']:
            messages.error(request, f'Only active or overdue bookings can be flagged. Current status: {booking.status}.')
            return redirect('admin_bookings')

        if booking.status == 'active' and booking.end_date >= timezone.localdate():
            messages.error(request, 'This booking is not overdue yet.')
            return redirect('admin_bookings')

        was_active = booking.status == 'active'
        if was_active:
            booking.status = 'overdue'
            booking.save(update_fields=['status', 'updated_at'])

        overdue_days = max((timezone.localdate() - booking.end_date).days, 1)
        related_url = f'/dashboard/?booking={booking.booking_id}'
        already_notified_today = Notification.objects.filter(
            user=booking.borrower,
            notification_type='booking_overdue',
            related_url=related_url,
            created_at__date=timezone.localdate(),
        ).exists()

        if not already_notified_today:
            Notification.objects.create(
                user=booking.borrower,
                notification_type='booking_overdue',
                title='Overdue Item Notice',
                message=(
                    f'Your booking for {booking.item.name} is overdue by {overdue_days} day(s). '
                    'Please return the item as soon as possible or contact support if you need an extension.'
                ),
                related_url=related_url,
            )

        BookingHistory.objects.create(
            booking=booking,
            action='overdue',
            performed_by=request.user,
            notes='Flagged as overdue by admin and borrower notified.' if was_active else 'Overdue reminder sent by admin.',
        )

        messages.success(
            request,
            f'Overdue notice sent to {booking.borrower.username} for "{booking.item.name}".' if not already_notified_today
            else f'"{booking.item.name}" is already flagged overdue and {booking.borrower.username} was already notified today.'
        )

    return redirect('admin_bookings')

# ======================
# PROFILE VIEWS
# ======================

@login_required
def profile_view(request):
    """User profile page"""
    user = request.user

    recent_activity = []

    recent_bookings = Booking.objects.filter(
        borrower=user
    ).select_related('item').order_by('-created_at')[:6]

    for booking in recent_bookings:
        badge_map = {
            'pending': ('Pending', 'warning'),
            'approved': ('Approved', 'info'),
            'paid': ('Paid', 'success'),
            'active': ('Active', 'success'),
            'completed': ('Completed', 'info'),
            'cancelled': ('Cancelled', 'danger'),
            'declined': ('Declined', 'danger'),
            'overdue': ('Overdue', 'danger'),
        }
        badge_text, badge_class = badge_map.get(booking.status, (booking.get_status_display(), 'info'))
        recent_activity.append({
            'title': 'You borrowed',
            'description': booking.item.name,
            'timestamp': booking.created_at,
            'icon': 'fa-hand-holding',
            'badge_text': badge_text,
            'badge_class': badge_class,
        })

    recent_suggestions = ItemSuggestion.objects.filter(
        suggested_by=user
    ).order_by('-created_at')[:4]

    for suggestion in recent_suggestions:
        recent_activity.append({
            'title': 'You suggested',
            'description': suggestion.name,
            'timestamp': suggestion.created_at,
            'icon': 'fa-lightbulb',
            'badge_text': suggestion.get_status_display(),
            'badge_class': 'info' if suggestion.status in ['approved', 'campaign_created'] else 'warning',
        })

    recent_contributions = Contribution.objects.filter(
        user=user
    ).select_related('campaign').order_by('-created_at')[:4]

    for contribution in recent_contributions:
        recent_activity.append({
            'title': 'You contributed',
            'description': f'Ksh {contribution.amount} to {contribution.campaign.title}',
            'timestamp': contribution.created_at,
            'icon': 'fa-coins',
            'badge_text': 'Contribution',
            'badge_class': 'success',
        })

    recent_reviews = Review.objects.filter(
        reviewee=user
    ).select_related('reviewer').order_by('-created_at')[:4]

    for review in recent_reviews:
        recent_activity.append({
            'title': f'You received a {review.rating}-star review',
            'description': f'from {review.reviewer.username}',
            'timestamp': review.created_at,
            'icon': 'fa-star',
            'badge_text': 'Review',
            'badge_class': 'info',
        })

    admin_actions = BookingHistory.objects.filter(
        performed_by=user
    ).select_related('booking__item', 'booking__borrower').order_by('-timestamp')[:4]

    for action in admin_actions:
        booking = action.booking
        if booking is None:
            continue
        recent_activity.append({
            'title': f'You updated booking {booking.booking_id}',
            'description': f'{action.get_action_display()} for {booking.item.name}',
            'timestamp': action.timestamp,
            'icon': 'fa-user-check',
            'badge_text': 'Admin',
            'badge_class': 'warning',
        })

    notifications = Notification.objects.filter(
        user=user
    ).order_by('-created_at')[:4]

    for notification in notifications:
        recent_activity.append({
            'title': notification.title,
            'description': notification.message,
            'timestamp': notification.created_at,
            'icon': 'fa-bell',
            'badge_text': 'Unread' if not notification.is_read else 'Read',
            'badge_class': 'warning' if not notification.is_read else 'info',
        })

    recent_activity = sorted(recent_activity, key=lambda activity: activity['timestamp'], reverse=True)[:12]

    if request.user.is_admin_approved:
        template = 'admin/profile.html'
    else:
        template = 'profile.html'
    return render(request, template, {
        'user': user,
        'recent_activity': recent_activity,
    })

@login_required
def update_profile(request):
    """Update user profile"""
    if request.method == 'POST':
        user = request.user

        requested_username = (request.POST.get('username') or '').strip()
        requested_email = (request.POST.get('email') or '').strip()

        if not requested_username:
            messages.error(request, 'Username is required.')
            return redirect('profile')

        username_taken = CustomUser.objects.filter(username__iexact=requested_username).exclude(id=user.id).exists()
        if username_taken:
            messages.error(request, 'That username is already taken. Please choose another one.')
            return redirect('profile')

        if not requested_email:
            messages.error(request, 'Email is required.')
            return redirect('profile')

        user.username = requested_username
        user.first_name = (request.POST.get('first_name') or '').strip()
        user.last_name = (request.POST.get('last_name') or '').strip()
        user.email = requested_email
        user.phone_number = (request.POST.get('phone_number') or '').strip()
        user.location = (request.POST.get('location') or '').strip()
        user.bio = (request.POST.get('bio') or '').strip()
        
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return redirect('profile')

@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        current = request.POST.get('current_password')
        new = request.POST.get('new_password')
        confirm = request.POST.get('confirm_password')
        
        if not request.user.check_password(current):
            messages.error(request, 'Current password is incorrect')
        elif new != confirm:
            messages.error(request, 'New passwords do not match')
        elif len(new) < 8:
            messages.error(request, 'Password must be at least 8 characters')
        else:
            request.user.set_password(new)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully!')
        
        return redirect('profile')
    
    return redirect('profile')


@login_required
def delete_account(request):
    """Delete currently authenticated user's account."""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method for account deletion.')
        return redirect('profile')

    confirmation = (request.POST.get('delete_confirmation') or '').strip().upper()
    if confirmation != 'DELETE':
        messages.error(request, 'Please type DELETE to confirm account deletion.')
        return redirect('profile')

    user = request.user
    username = user.username

    # End the current session before deleting the user record.
    auth_logout(request)
    user.delete()

    messages.success(request, f'Account "{username}" has been deleted successfully.')
    return redirect('index')


# ======================
# EMAIL VERIFICATION VIEWS
# ======================
def verify_email(request, token):
    """Verify email with token using EmailVerificationToken model"""
    try:
        verification = EmailVerificationToken.objects.get(token=token)
        
        if verification.is_valid():
            user = verification.user
            user.email_verified = True
            user.verification_level = 1  # Email Verified level
            user.is_active = True  # Make sure user is active
            user.save()
            
            # Delete the token (already used)
            verification.delete()
            
            # Log the user in
            from django.contrib.auth import login
            login(request, user)
            
            # Force session save
            request.session.save()
            
            # Print debug info
            print(f"✅ User {user.username} logged in")
            print(f"   Session key: {request.session.session_key}")
            
            messages.success(request, 'Email verified successfully! You can now access all features.')
            
            # Redirect based on role
            if user.is_admin_approved:
                return redirect('/admin-dashboard/')
            else:
                return redirect('/dashboard/')
        else:
            messages.error(request, 'Verification link has expired. Please request a new one.')
            return redirect('resend_verification')
            
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('login')






def verify_email_pending(request):
    """Page showing verification pending"""
    # Check if user is authenticated
    if not request.user.is_authenticated:
        messages.warning(request, 'Please login first to verify your email.')
        return redirect('login')
    
    # Check if user is already verified
    if request.user.email_verified:
        messages.info(request, 'Your email is already verified.')
        if request.user.is_admin_approved:
            return redirect('admin_dashboard')
        return redirect('user_dashboard')

    if request.method == 'POST':
        submitted_token = (request.POST.get('verification_token') or '').strip().upper()
        if not submitted_token:
            messages.error(request, 'Please enter the verification token from your email. It expires after 30 minutes.')
            return redirect('verify_email_pending')

        verification = EmailVerificationToken.objects.filter(
            user=request.user,
            token=submitted_token
        ).first()

        if verification is None:
            messages.error(request, 'Invalid token. Please check the token and try again.')
            return redirect('verify_email_pending')

        if not verification.is_valid():
            verification.delete()
            messages.error(request, 'That token has expired after 30 minutes. Please request a new verification token.')
            return redirect('verify_email_pending')

        user = request.user
        user.email_verified = True
        user.verification_level = max(user.verification_level, 1)
        user.is_active = True
        user.save(update_fields=['email_verified', 'verification_level', 'is_active'])
        verification.delete()

        messages.success(request, 'Email verified successfully! Your account is now active.')
        if user.is_admin_approved:
            return redirect('admin_dashboard')
        return redirect('user_dashboard')
    
    return render(request, 'registration/verify-email-pending.html', {'user': request.user})



@login_required
def resend_verification(request):
    """Resend verification email"""
    print("=" * 50)
    print("🔍 RESEND VERIFICATION STARTED")
    
    if not request.user.is_authenticated:
        messages.error(request, 'Please login first.')
        return redirect('/login/')
    
    print(f"User: {request.user.username}, Email: {request.user.email}")
    print(f"Email verified: {request.user.email_verified}")
    
    if request.user.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('/dashboard/')
    
    # Create/rotate token for manual verification
    token = _create_or_rotate_email_verification_token(request.user)
    print(f"✅ New token created: {token}")
    
    # Build verification link
    verification_link = _build_verification_link(request, token)
    print(f"🔗 Verification link: {verification_link}")
    
    # Prepare email content
    subject = 'Verify Your Email - Knot'
    
    try:
        html_message = render_to_string('emails/verify_email.html', {
            'user': request.user,
            'link': verification_link,
            'token': token,
            'site_name': 'Knot',
            'expires_in': '30 minutes'
        })
        print("✅ HTML template rendered successfully")
    except Exception as e:
        print(f"❌ Failed to render template: {e}")
        messages.error(request, 'Error preparing email. Please try again.')
        return redirect('/accounts/verify-email-pending/')
    
    plain_message = strip_tags(html_message)
    
    # Send the email
    print(f"📧 Attempting to send email to: {request.user.email}")
    print(f"From: {settings.DEFAULT_FROM_EMAIL}")
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        print(f"✅✅✅ EMAIL SENT SUCCESSFULLY to {request.user.email}!")
        messages.success(request, f'Verification email sent to {request.user.email}! Please check your inbox.')
    except Exception as e:
        print(f"❌❌❌ FAILED TO SEND EMAIL: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        messages.warning(request, 'Could not send email right now. Please try again in a moment.')
    
    return redirect('/accounts/verify-email-pending/')


@login_required
@email_verified_required
def request_admin_access(request):
    """Allow a verified member to request admin access from their dashboard."""
    if request.method != 'POST':
        return redirect('user_dashboard')

    user = request.user

    if user.is_superuser or user.is_staff or user.is_admin_approved:
        messages.info(request, 'Your account already has admin access.')
        return redirect('user_dashboard')

    if user.admin_request_status == 'pending':
        messages.info(request, 'Your admin access request is already pending review.')
        return redirect('user_dashboard')

    reason = (request.POST.get('admin_reason') or '').strip()
    if not reason:
        messages.error(request, 'Please add a reason before requesting admin access.')
        return redirect('user_dashboard')

    admin_id_photo = request.FILES.get('admin_id_photo')
    if not admin_id_photo and not user.admin_request_id_photo:
        messages.error(request, 'Please upload an ID photo when requesting admin access.')
        return redirect('user_dashboard')

    if admin_id_photo:
        id_photo_error = _validate_admin_id_photo(admin_id_photo)
        if id_photo_error:
            messages.error(request, id_photo_error)
            return redirect('user_dashboard')

    user.admin_request_status = 'pending'
    user.admin_request_reason = reason
    if admin_id_photo:
        user.admin_request_id_photo = admin_id_photo
    user.admin_request_date = timezone.now()
    user.admin_request_reviewed_by = None
    user.admin_request_review_date = None
    user.admin_request_review_notes = ''
    user.save(update_fields=[
        'admin_request_status',
        'admin_request_reason',
        'admin_request_id_photo',
        'admin_request_date',
        'admin_request_reviewed_by',
        'admin_request_review_date',
        'admin_request_review_notes',
    ])

    messages.success(request, 'Your admin access request has been submitted for review.')
    return redirect('user_dashboard')


@login_required
@email_verified_required
def request_pickup_time_change(request, booking_id):
    """Allow borrower to message admin/steward when pickup time does not work."""
    if request.method != 'POST':
        return redirect('user_dashboard')

    booking = get_object_or_404(
        Booking.objects.select_related('item', 'steward', 'item__steward', 'borrower'),
        id=booking_id,
        borrower=request.user,
    )

    if booking.status not in ['approved', 'paid']:
        messages.error(request, 'Pickup time change requests are only available for approved or paid bookings.')
        return redirect(f"{reverse('user_dashboard')}#bookings")

    recipient = booking.steward or booking.item.steward
    if not recipient:
        messages.error(request, 'No admin is assigned to this booking yet. Please try again shortly.')
        return redirect(f"{reverse('user_dashboard')}#bookings")

    message_body = (request.POST.get('message') or '').strip()
    preferred_date = (request.POST.get('preferred_pickup_date') or '').strip()
    preferred_time = (request.POST.get('preferred_pickup_time') or '').strip()

    if not message_body:
        messages.error(request, 'Please add a message for the admin before sending your request.')
        return redirect(f"{reverse('user_dashboard')}#bookings")

    subject = f'Pickup Time Change Request - {booking.booking_id}'
    conversation = Conversation.objects.filter(
        related_booking=booking,
        participants=request.user,
    ).filter(
        participants=recipient,
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(
            subject=subject,
            related_item=booking.item,
            related_booking=booking,
        )
        conversation.participants.add(request.user, recipient)
    elif not conversation.subject:
        conversation.subject = subject
        conversation.save(update_fields=['subject'])

    lines = [
        f'Pickup time change request for booking {booking.booking_id} ({booking.item.name}).',
        f'Current pickup schedule: {booking.pickup_date or "Not set"} at {booking.pickup_time or "Not set"}.',
    ]
    if preferred_date or preferred_time:
        lines.append(
            f'Preferred pickup schedule: {preferred_date or "Date not specified"} at {preferred_time or "Time not specified"}.'
        )
    lines.append('')
    lines.append(message_body)

    Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content='\n'.join(lines),
    )

    # Touch the thread so it moves to the top.
    conversation.save(update_fields=['updated_at'])

    Notification.objects.create(
        user=recipient,
        notification_type='new_message',
        title='Pickup Time Change Request',
        message=(
            f'{request.user.username} requested a pickup time change for '
            f'booking {booking.booking_id} ({booking.item.name}).'
        ),
        related_url=f'/accounts/bookings/review/{booking.id}/',
    )

    messages.success(request, 'Your pickup time change request has been sent to the admin.')
    return redirect(f"{reverse('user_dashboard')}#bookings")


def _resolve_booking_chat_recipient(sender, booking):
    """Pick the chat recipient based on whether sender is borrower or admin/steward."""
    if sender == booking.borrower:
        return booking.steward or booking.item.steward
    return booking.borrower


def _sender_initials(user):
    full_name = (user.get_full_name() or '').strip()
    source = full_name or user.username
    parts = [p for p in source.replace('_', ' ').split() if p]
    if not parts:
        return 'U'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _get_or_create_booking_conversation(booking, sender, recipient):
    conversation = Conversation.objects.filter(
        related_booking=booking,
        participants=sender,
    ).filter(
        participants=recipient,
    ).order_by('-updated_at').first()

    if conversation:
        if not conversation.subject:
            conversation.subject = f'Pickup Chat - {booking.booking_id}'
            conversation.save(update_fields=['subject'])
        return conversation

    conversation = Conversation.objects.create(
        subject=f'Pickup Chat - {booking.booking_id}',
        related_item=booking.item,
        related_booking=booking,
    )
    conversation.participants.add(sender, recipient)
    return conversation


def _can_access_booking_chat(user, booking):
    if user == booking.borrower:
        return True
    if user == booking.steward or user == booking.item.steward:
        return True
    return user.is_superuser or user.is_staff or user.is_admin_approved


@login_required
@email_verified_required
def booking_chat_messages(request, booking_id):
    """Return booking chat messages in JSON for chat-style UI."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(
        Booking.objects.select_related('borrower', 'steward', 'item__steward', 'item'),
        id=booking_id,
    )

    if not _can_access_booking_chat(request.user, booking):
        return JsonResponse({'error': 'You cannot access this booking chat.'}, status=403)

    base_messages_qs = Message.objects.filter(
        conversation__related_booking=booking,
    ).select_related('sender').order_by('created_at')

    messages_qs = base_messages_qs[:120]

    # Mark inbound messages as read for the current user.
    unread_messages = base_messages_qs.exclude(sender=request.user).filter(is_read=False)
    for msg in unread_messages:
        msg.mark_as_read()

    payload = [
        {
            'id': msg.id,
            'sender': msg.sender.username,
            'sender_id': msg.sender_id,
            'sender_initials': _sender_initials(msg.sender),
            'content': msg.content,
            'is_mine': msg.sender_id == request.user.id,
            'created_at': timezone.localtime(msg.created_at).strftime('%b %d, %Y %I:%M %p'),
            'created_at_relative': f"{timesince(msg.created_at)} ago",
        }
        for msg in messages_qs
    ]

    return JsonResponse({
        'booking_id': booking.id,
        'booking_code': booking.booking_id,
        'item_name': booking.item.name,
        'messages': payload,
    })


@login_required
@email_verified_required
def booking_chat_send(request, booking_id):
    """Send a booking chat message (borrower <-> admin/steward)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    booking = get_object_or_404(
        Booking.objects.select_related('borrower', 'steward', 'item__steward', 'item'),
        id=booking_id,
    )

    if not _can_access_booking_chat(request.user, booking):
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'You cannot message for this booking.'}, status=403)
        messages.error(request, 'You cannot message for this booking.')
        return redirect('user_dashboard')

    payload = {}
    if request.headers.get('Content-Type', '').startswith('application/json'):
        try:
            import json
            payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            payload = {}

    message_body = (
        payload.get('message')
        or request.POST.get('message')
        or ''
    ).strip()
    preferred_date = (
        payload.get('preferred_pickup_date')
        or request.POST.get('preferred_pickup_date')
        or ''
    ).strip()
    preferred_time = (
        payload.get('preferred_pickup_time')
        or request.POST.get('preferred_pickup_time')
        or ''
    ).strip()

    if not message_body:
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'Message cannot be empty.'}, status=400)
        messages.error(request, 'Message cannot be empty.')
        return redirect(request.POST.get('next') or f"{reverse('user_dashboard')}#bookings")

    recipient = _resolve_booking_chat_recipient(request.user, booking)
    if recipient is None:
        if request.headers.get('Content-Type', '').startswith('application/json'):
            return JsonResponse({'error': 'No chat recipient is currently available for this booking.'}, status=400)
        messages.error(request, 'No chat recipient is currently available for this booking.')
        return redirect(request.POST.get('next') or f"{reverse('user_dashboard')}#bookings")

    conversation = _get_or_create_booking_conversation(booking, request.user, recipient)

    message_text = message_body
    if preferred_date or preferred_time:
        message_text = (
            f"Preferred pickup: {preferred_date or 'Date not specified'} at {preferred_time or 'Time not specified'}.\n"
            f"{message_body}"
        )

    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content=message_text,
    )
    conversation.save(update_fields=['updated_at'])

    Notification.objects.create(
        user=recipient,
        notification_type='new_message',
        title='New Booking Chat Message',
        message=(
            f'{request.user.username} sent a message about booking '
            f'{booking.booking_id} ({booking.item.name}).'
        ),
        related_url=f'/accounts/bookings/review/{booking.id}/',
    )

    if request.headers.get('Content-Type', '').startswith('application/json'):
        return JsonResponse({
            'status': 'ok',
            'message': {
                'id': message.id,
                'sender': request.user.username,
                'sender_initials': _sender_initials(request.user),
                'content': message.content,
                'created_at': timezone.localtime(message.created_at).strftime('%b %d, %Y %I:%M %p'),
                'created_at_relative': f"{timesince(message.created_at)} ago",
            }
        })

    messages.success(request, 'Message sent.')
    return redirect(request.POST.get('next') or f'/accounts/bookings/review/{booking.id}/')