import os
import sys

# Setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.filter(is_active=True, email_verified=True).first()
print("User:", user.username if user else "None")

if user:
    c = Client()
    c.force_login(user)
    r = c.get('/dashboard/')
    print("Status:", r.status_code)
    content = r.content.decode('utf-8')
    placeholder = content.count('via.placeholder.com')
    real = content.count('media/item_images')
    print("Placeholder images:", placeholder)
    print("Real images:", real)
