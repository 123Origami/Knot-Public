from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'transactions', views.TransactionViewSet)
router.register(r'contributions', views.ContributionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # Payment initiation
    path('mpesa/initiate/', views.InitiateMpesaPaymentView.as_view(), name='initiate_mpesa'),
    path('card/initiate/', views.InitiateCardPaymentView.as_view(), name='initiate_card'),
    
    # Webhook
    path('webhook/', views.payhero_webhook, name='payhero_webhook'),
    
    # Success page
    path('success/', views.PaymentSuccessView.as_view(), name='payment_success'),
    
    # Admin: Payouts
    path('payout/initiate/', views.InitiatePayoutView.as_view(), name='initiate_payout'),
]