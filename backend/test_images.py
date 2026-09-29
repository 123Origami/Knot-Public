#!/usr/bin/env python
import os
import sys
import django

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.bookings.models import Booking
from apps.items.models import ItemImage

u = get_user_model().objects.filter(is_active=True, email_verified=True).first()
print(f"User: {u.username if u else 'None'}")

if u:
    bookings = Booking.objects.filter(borrower=u).select_related('item').prefetch_related('item__images')
    print(f"Bookings: {bookings.count()}")
    
    for i, b in enumerate(bookings[:3]):
        print(f"\nBooking {i+1}: {b.booking_id}")
        print(f"  Item: {b.item.name}")
        print(f"  Item ID: {b.item.id}")
        
        # Check images directly
        images = ItemImage.objects.filter(item=b.item)
        print(f"  Total images: {images.count()}")
        
        for img in images:
            print(f"    - {img.id}: {img.image.name} (primary={img.is_primary})")
        
        # Check primary_image property
        primary = b.item.primary_image
        print(f"  primary_image property result: {primary}")
