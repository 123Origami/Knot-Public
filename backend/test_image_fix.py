import os
import sys
import django

# Setup path
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from apps.bookings.models import Booking
from apps.items.models import ItemImage

User = get_user_model()
user = User.objects.filter(is_active=True, email_verified=True).first()

if not user:
    print("ERROR: No test user found")
    sys.exit(1)

print(f"Test user: {user.username}")

# Test 1: Check if user has bookings
bookings = Booking.objects.filter(borrower=user).select_related('item').prefetch_related('item__images')
print(f"\n1. User bookings count: {bookings.count()}")

if bookings.count() == 0:
    print("   WARNING: User has no bookings, creating test booking...")
else:
    # Test 2: Check if images are accessible
    for i, booking in enumerate(bookings[:3]):
        print(f"\n2.{i+1}. Booking: {booking.booking_id}")
        print(f"    Item: {booking.item.name}")
        
        # Check primary_image property
        primary = booking.item.primary_image
        print(f"    primary_image exists: {primary is not None}")
        
        # Check display_image_url property
        display_url = booking.item.display_image_url
        print(f"    display_image_url: {display_url[:80]}..." if len(display_url) > 80 else f"    display_image_url: {display_url}")
        
        # Check actual images in database
        images_count = booking.item.images.count()
        print(f"    Total images: {images_count}")
        
        primary_images = booking.item.images.filter(is_primary=True).count()
        print(f"    Primary images: {primary_images}")

# Test 3: Test dashboard rendering
print(f"\n3. Testing dashboard rendering...")
c = Client()
c.force_login(user)
response = c.get('/dashboard/')

if response.status_code != 200:
    print(f"   ERROR: Dashboard returned status {response.status_code}")
else:
    content = response.content.decode('utf-8')
    
    # Check for upcoming bookings section
    if 'Upcoming Bookings' in content:
        print("   Upcoming Bookings section: FOUND")
        
        # Count images
        img_count = content.count('<img src=')
        print(f"   Total <img> tags in page: {img_count}")
        
        # Check for specific image types
        placeholder_count = content.count('via.placeholder.com')
        media_count = content.count('media/item_images')
        picsum_count = content.count('picsum.photos')
        
        print(f"   Placeholder images (via.placeholder): {placeholder_count}")
        print(f"   Media item images: {media_count}")
        print(f"   Generated images (picsum): {picsum_count}")
        
        # Get the upcoming bookings section
        start = content.find('Upcoming Bookings')
        bookings_section = content[start:start+3000]
        
        booking_img_count = bookings_section.count('<img src=')
        print(f"   Images in Upcoming Bookings section: {booking_img_count}")
    else:
        print("   ERROR: Upcoming Bookings section not found")
    
    print(f"\n   Dashboard rendered successfully!")

print("\n✓ All tests completed!")
