import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

# Get an authenticated user
User = get_user_model()
user = User.objects.filter(is_active=True, email_verified=True).first()

if user:
    c = Client()
    c.force_login(user)
    response = c.get('/dashboard/')
    
    # Check if the response contains image tags
    content = response.content.decode('utf-8')
    
    print(f"Response status: {response.status_code}")
    print(f"Has 'table-item' divs: {'table-item' in content}")
    print(f"Has img tags in booking table: {content.count('<img src=')}")
    
    # Count placeholder images vs real images
    placeholder_count = content.count('via.placeholder.com')
    real_image_count = content.count('media/item_images')
    
    print(f"Placeholder images: {placeholder_count}")
    print(f"Real item images: {real_image_count}")
    
    # Check for upcoming bookings section
    if 'Upcoming Bookings' in content:
        print("Upcoming Bookings section: Found")
        # Find the section and check for images
        start = content.find('Upcoming Bookings')
        section = content[start:start+2000]
        if '<img' in section:
            print("Images found in section: Yes")
        else:
            print("Images found in section: No")
else:
    print("No test user found")
