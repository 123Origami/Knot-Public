from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.filter(is_active=True, email_verified=True).first()

if user:
    print(f"Test user: {user.username}")
    
    c = Client()
    c.force_login(user)
    response = c.get('/dashboard/')
    print(f"Status: {response.status_code}")
    
    content = response.content.decode('utf-8')
    
    # Check image counts
    has_upcoming = 'Upcoming Bookings' in content
    img_total = content.count('<img src=')
    placeholder = content.count('via.placeholder.com')
    media = content.count('media/item_images')
    picsum = content.count('picsum.photos')
    
    print(f"Upcoming Bookings section: {has_upcoming}")
    print(f"Total images in page: {img_total}")
    print(f"Placeholder images: {placeholder}")
    print(f"Media images: {media}")
    print(f"Picsum images: {picsum}")
    
    # Get bookings section
    if has_upcoming:
        start = content.find('Upcoming Bookings')
        section = content[start:start+2500]
        booking_imgs = section.count('<img src=')
        print(f"Images in bookings table: {booking_imgs}")
else:
    print("No test user found")
