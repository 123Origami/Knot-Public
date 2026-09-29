"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import re
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.views.static import serve as serve_static
from apps.accounts.views import signup, login
from apps.items import views as item_views
from . import views

urlpatterns = [
    # Django Admin (keep this first)
    path('admin/', admin.site.urls),
    
    # Homepage
    path('', views.index, name='index'),
    
    # Authentication
    path('login/', login, name='login'),  # This now uses accounts.views.login
    path('signup/', signup, name='signup'),  # Uses backend.views.signup
    path('logout/', views.logout_view, name='logout'), 
    
    
    # Main Pages
    path('browse/', views.browse, name='browse'),
    path('goals/', views.goals, name='goals'),
    path('suggest/', views.suggest, name='suggest'),
    
    # Other Pages
    path('item-detail/', views.item_detail, name='item_detail'),
    path('book-item/<int:item_id>/', views.book_item, name='book_item'),
    path('items/<slug:slug>/book/', item_views.book_item_page, name='book_item_slug'),
    
    # Dashboards - USE DIFFERENT PATHS!
    path('dashboard/', views.user_dashboard, name='user_dashboard'),  # Regular user dashboard
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),  # Admin dashboard

    # Admin Page (rename to avoid conflict with Django admin)
    path('admin-page/', views.admin, name='admin_page'),

    path('accounts/', include('apps.accounts.urls')),

    # API Authentication URLs (your DRF endpoints)
    path('api/auth/', include('apps.accounts.urls')),
    path('api/campaigns/', include('apps.campaigns.urls')),
    path('api/core/', include('apps.core.urls')),

    # Email verification URLs (from the package)
    path('verification/', include('verify_email.urls')),

    #campain details page

    path('campaigns/<int:campaign_id>/', views.campaign_detail, name='campaign_detail'),

    # Informational pages
    path('how-it-works/', views.info_page, {'page_key': 'how-it-works'}, name='how_it_works'),
    path('help-center/', views.info_page, {'page_key': 'help-center'}, name='help_center'),
    path('community-guidelines/', views.info_page, {'page_key': 'community-guidelines'}, name='community_guidelines'),
    path('safety-tips/', views.info_page, {'page_key': 'safety-tips'}, name='safety_tips'),
    path('contact-us/', views.info_page, {'page_key': 'contact-us'}, name='contact_us'),
    path('terms-of-service/', views.info_page, {'page_key': 'terms-of-service'}, name='terms_of_service'),
    path('privacy-policy/', views.info_page, {'page_key': 'privacy-policy'}, name='privacy_policy'),
    path('cookie-policy/', views.info_page, {'page_key': 'cookie-policy'}, name='cookie_policy'),

    # Items API
    path('api/items/', include('apps.items.urls')),
    
    # Bookings API
    path('api/bookings/', include('apps.bookings.urls')),

    # Reviews API
    path('api/reviews/', include('apps.reviews.urls')),
    
    # Items HTML pages
    path('items/', include('apps.items.urls')),
   
]

# Served by Django directly (not just in DEBUG) since this project has no
# separate object storage/CDN for user-uploaded media. Django's own
# django.conf.urls.static.static() helper silently no-ops when DEBUG=False,
# so the URL pattern is registered by hand here instead.
urlpatterns += [
    re_path(
        r'^%s(?P<path>.*)$' % re.escape(settings.MEDIA_URL.lstrip('/')),
        serve_static,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
