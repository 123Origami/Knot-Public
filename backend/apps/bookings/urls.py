from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BookingViewSet, CreateBookingView, booking_payment_callback

router = DefaultRouter()
router.register(r'bookings', BookingViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('create/', CreateBookingView.as_view(), name='create-booking'),
    path('payment-callback/', booking_payment_callback, name='booking-payment-callback'),
]