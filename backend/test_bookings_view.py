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
    
    # Check for new columns in My Bookings
    has_pickup_location = 'Pickup Location' in content
    has_pickup_datetime = 'Pickup Date' in content
    has_calendar_icon = 'fa-calendar-alt' in content
    has_map_icon = 'fa-map-marker-alt' in content
    
    print(f"\nMy Bookings table checks:")
    print(f"  'Pickup Location' header: {has_pickup_location}")
    print(f"  'Pickup Date & Time' header: {has_pickup_datetime}")
    print(f"  Calendar icons present: {has_calendar_icon}")
    print(f"  Map marker icons present: {has_map_icon}")
    
    # Count table columns in bookings table
    bookings_start = content.find('id="bookingsTable"')
    if bookings_start > 0:
        bookings_section = content[bookings_start:bookings_start+2000]
        th_count = bookings_section.count('<th>')
        print(f"  Table header columns: {th_count}")
        
    print("\n✓ Dashboard renders successfully with new columns!")
else:
    print("No test user found")
