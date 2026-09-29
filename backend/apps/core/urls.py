from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'notifications', views.NotificationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('site-settings/', views.SiteSettingsView.as_view(), name='site-settings'),
]