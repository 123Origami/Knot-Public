from django.urls import path
from . import views

urlpatterns = [
    # Public campaign views
       # Test endpoint
    path('test-ngrok/', views.test_ngrok, name='test-ngrok'),
    
    # Campaign endpoints
    path('campaigns/', views.CampaignListView.as_view(), name='campaign-list'),
    path('campaigns/statistics/', views.CampaignStatisticsView.as_view(), name='campaign-stats'),
    path('campaigns/recent/', views.RecentContributionsView.as_view(), name='recent-contributions'),
    path('campaigns/<int:campaign_id>/contributors/', views.CampaignContributorsView.as_view(), name='campaign-contributors'),
    
    # Contribution endpoints
    path('campaigns/<int:campaign_id>/contribute/', views.CreateContributionView.as_view(), name='create-contribution'),
    path('campaigns/<int:campaign_id>/pullout/', views.CampaignPulloutView.as_view(), name='campaign-pullout'),

    
    # Payment callback
    path('verify-payment/', views.VerifyPaymentView.as_view(), name='verify-payment'),
    path('campaigns/<int:campaign_id>/contribute/', views.CreateContributionView.as_view(), name='create-contribution'),
    path('payment-callback/', views.payhero_callback, name='payhero-callback'),
    path('check-payment-status/', views.CheckPaymentStatusView.as_view(), name='check-payment-status'),

     # User contributions
    path('contributions/my/', views.UserContributionsView.as_view(), name='my-contributions'),
    
    # Single campaign detail (for refreshing after contribution)
    path('campaigns/<int:campaign_id>/detail/', views.CampaignDetailView.as_view(), name='campaign-detail'),

    #test
    path('test-callback/', views.test_callback, name='test_callback'),
]