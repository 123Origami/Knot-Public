from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url='login'):
    """
    Decorator for views that checks if the user is an approved admin.
    """
    def check_admin(user):
        if not user.is_authenticated:
            return False
        return user.is_superuser or user.is_staff or getattr(user, 'is_admin_approved', False)
    
    actual_decorator = user_passes_test(
        check_admin,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator



def email_verified_required(view_func):
    """Decorator to require email verification for access"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if not request.user.email_verified and settings.REQUIRE_EMAIL_VERIFICATION:
            messages.warning(request, 'Please verify your email before accessing this page.')
            return redirect('verify_email_pending')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view