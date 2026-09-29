from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Authentication
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='api_login'),  # Renamed to api_login
    path('logout/', views.LogoutView.as_view(), name='api_logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Email verification
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),  # Template view
    path('verify-email/api/<str:token>/', views.VerifyEmailView.as_view(), name='api_verify_email'),  # API view
    path('verify-email-pending/', views.verify_email_pending, name='verify_email_pending'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),  # Template view
    path('resend-verification/api/', views.ResendVerificationView.as_view(), name='api_resend_verification'),  # API view
    path('verify/', include('verify_email.urls')),
    
    # Password reset
    path('password-reset/', views.RequestPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/<str:token>/', views.ResetPasswordView.as_view(), name='reset_password'),
    
    # Profile (template views)
    path('profile/', views.profile_view, name='profile'),
    path('admin/request-access/', views.request_admin_access, name='request_admin_access'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('profile/<str:username>/', views.user_profile_detail, name='profile_detail'),
    path('profile/change-password/', views.change_password, name='change_password'),
    # Profile API endpoints
    path('profile/api/', views.ProfileView.as_view(), name='profile_api'),
    path('profile/api/update/', views.UpdateProfileView.as_view(), name='profile_update_api'),
    # Admin
    path('admin/requests/', views.admin_request_list, name='admin_request_list'),
    path('admin/requests/approve/<int:user_id>/', views.admin_request_approve, name='admin_request_approve'),
    path('admin/requests/reject/<int:user_id>/', views.admin_request_reject, name='admin_request_reject'),
    path('admin/requests/bulk-action/', views.admin_request_bulk_action, name='admin_request_bulk_action'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/export/', views.admin_users_export_csv, name='admin_users_export_csv'),
    path('items/', views.admin_items, name='admin_items'),
    path('suggestions/', views.admin_suggestions, name='admin_suggestions'),
    path('bookings/', views.admin_bookings, name='admin_bookings'),
    path('reports/', views.admin_reports, name='admin_reports'),
    path('users/activate/<int:user_id>/', views.admin_user_activate, name='admin_user_activate'),
    path('users/deactivate/<int:user_id>/', views.admin_user_deactivate, name='admin_user_deactivate'),
    path('users/delete/<int:user_id>/', views.admin_user_delete, name='admin_user_delete'),
    path('items/status/<int:item_id>/', views.admin_item_update_status, name='admin_item_update_status'),
    path('items/create/', views.admin_item_create, name='admin_item_create'),
    path('items/edit/<int:item_id>/', views.admin_item_edit, name='admin_item_edit'),
    path('items/delete/<int:item_id>/', views.admin_item_delete, name='admin_item_delete'),
    path('bookings/approve/<int:booking_id>/', views.admin_booking_approve, name='admin_booking_approve'),
    path('bookings/reject/<int:booking_id>/', views.admin_booking_reject, name='admin_booking_reject'),
    path('bookings/request-pickup-change/<int:booking_id>/', views.request_pickup_time_change, name='request_pickup_time_change'),
    path('bookings/chat/<int:booking_id>/messages/', views.booking_chat_messages, name='booking_chat_messages'),
    path('bookings/chat/<int:booking_id>/send/', views.booking_chat_send, name='booking_chat_send'),
    path('bookings/review/<int:booking_id>/', views.admin_booking_review, name='admin_booking_review'),
    path('bookings/return/<int:booking_id>/', views.admin_booking_return, name='admin_booking_return'),
    path('bookings/checkout/<int:booking_id>/', views.admin_booking_checkout, name='admin_booking_checkout'),
    path('bookings/overdue/<int:booking_id>/', views.admin_booking_mark_overdue, name='admin_booking_mark_overdue'),
    path('settings/', views.admin_settings, name='admin_settings'),

]