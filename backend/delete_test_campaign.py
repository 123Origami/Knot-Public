import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from apps.campaigns.models import Campaign

# Find campaigns with "test 2" in the name
test_campaigns = Campaign.objects.filter(title__icontains='test 2')
print(f"Found {test_campaigns.count()} campaign(s) with 'test 2' in the title:")
for campaign in test_campaigns:
    print(f"  ID: {campaign.id}, Title: '{campaign.title}', Status: {campaign.status}")

# Delete them
if test_campaigns.exists():
    count, _ = test_campaigns.delete()
    print(f"\nDeleted {count} object(s)")
else:
    print("\nNo campaigns found with 'test 2' in the title")
