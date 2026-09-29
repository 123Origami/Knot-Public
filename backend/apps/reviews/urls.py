from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, UserReviewStatsView

router = DefaultRouter()
router.register(r'reviews', ReviewViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stats/<int:user_id>/', UserReviewStatsView.as_view(), name='user-review-stats'),
]