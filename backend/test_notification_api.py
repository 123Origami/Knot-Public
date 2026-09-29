import os
import sys
import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.core.models import Notification

User = get_user_model()
user = User.objects.filter(is_active=True, email_verified=True).first()

if user:
    print(f"Test user: {user.username}")
    
    # Create a test notification
    notif = Notification.objects.create(
        user=user,
        notification_type='system',
        title='Test Notification',
        message='This is a test notification',
        is_read=False
    )
    print(f"Created test notification: {notif.id}")
    
    # Test the API
    c = Client()
    c.force_login(user)
    
    # Test 1: Get notifications list
    response = c.get('/api/core/notifications/')
    print(f"\nTest 1 - GET /api/core/notifications/")
    print(f"  Status: {response.status_code}")
    
    # Test 2: Mark single notification as read
    response = c.post(
        '/api/core/notifications/mark_read/',
        {'notification_ids': [notif.id]},
        content_type='application/json'
    )
    print(f"\nTest 2 - POST /api/core/notifications/mark_read/ (single)")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    
    # Verify it was marked as read
    notif.refresh_from_db()
    print(f"  Notification is_read: {notif.is_read}")
    
    # Create another notification
    notif2 = Notification.objects.create(
        user=user,
        notification_type='system',
        title='Test Notification 2',
        message='This is another test',
        is_read=False
    )
    
    # Test 3: Mark all as read
    response = c.post(
        '/api/core/notifications/mark_read/',
        {'all': True},
        content_type='application/json'
    )
    print(f"\nTest 3 - POST /api/core/notifications/mark_read/ (all)")
    print(f"  Status: {response.status_code}")
    print(f"  Response: {response.json()}")
    
    # Verify both are marked as read
    notif2.refresh_from_db()
    print(f"  Notification 2 is_read: {notif2.is_read}")
    
    # Clean up
    notif.delete()
    notif2.delete()
    print("\n✓ All tests completed!")
else:
    print("No test user found")
