from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, EmailVerificationToken, PasswordResetToken

class CustomUserAdmin(UserAdmin):
    """Custom admin for User model"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'verification_level', 'is_active')
    list_filter = ('verification_level', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Verification Info', {'fields': ('verification_level', 'email_verified', 'phone_verified', 'id_verified')}),
        ('Contact Info', {'fields': ('phone_number', 'location')}),
        ('Profile', {'fields': ('profile_picture', 'bio')}),
        ('Reputation', {'fields': ('average_rating', 'total_reviews', 'successful_bookings', 'cancelled_bookings')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)