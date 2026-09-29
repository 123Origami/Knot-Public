from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from datetime import timedelta

from apps.campaigns.models import Campaign, Organization
from apps.items.models import Category, Item, ItemSuggestion

from .models import EmailVerificationToken

User = get_user_model()

class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_creation(self):
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.verification_level, 0)
    
    def test_verification_badge(self):
        self.assertEqual(self.user.get_verification_badge(), '🔴 Unverified')
        self.user.verification_level = 3
        self.assertEqual(self.user.get_verification_badge(), '⭐ Fully Verified')


class AdminSuggestionsCreateItemTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123',
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='testpass123',
        )
        self.category = Category.objects.create(name='Tools', slug='tools')
        self.organization = Organization.objects.create(
            name='Community Hub',
            slug='community-hub',
            description='A host organization for community goals.',
            address='Nairobi',
            contact_email='org@example.com',
            contact_phone='0700000000',
        )

    def test_create_item_from_funded_campaign_without_acquired_item_relation(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.member,
            name='Community Drill',
            description='A drill for neighborhood repair projects.',
            estimated_cost='5000.00',
            category=self.category,
            status='campaign_created',
        )
        campaign = Campaign.objects.create(
            title='Fund Community Drill',
            slug='fund-community-drill',
            description='Campaign for a shared drill.',
            target_amount='5000.00',
            funds_raised='5000.00',
            created_by=self.admin,
            host_organization=self.organization,
            end_date=timezone.now() + timedelta(days=30),
            category=self.category,
            suggested_item=suggestion,
            status='funded',
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('admin_suggestions'),
            {
                'action': 'create_item_from_campaign',
                'campaign_id': str(campaign.id),
                'location_details': 'Main tool room, shelf B',
                'condition': 'new',
                'max_borrow_days': '14',
                'daily_rate': '0',
                'deposit_amount': '500',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Item.objects.filter(campaign=campaign).exists())

    def test_create_item_from_campaign_can_create_new_category_when_missing(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.member,
            name='Community Table Saw',
            description='A shared table saw for local workshops.',
            estimated_cost='9000.00',
            category=None,
            status='campaign_created',
        )
        campaign = Campaign.objects.create(
            title='Fund Community Table Saw',
            slug='fund-community-table-saw',
            description='Campaign for a shared table saw.',
            target_amount='9000.00',
            funds_raised='9000.00',
            created_by=self.admin,
            host_organization=self.organization,
            end_date=timezone.now() + timedelta(days=30),
            category=None,
            suggested_item=suggestion,
            status='funded',
        )

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('admin_suggestions'),
            {
                'action': 'create_item_from_campaign',
                'campaign_id': str(campaign.id),
                'new_category_name': 'Woodworking',
                'location_details': 'Workshop A',
                'condition': 'new',
                'max_borrow_days': '10',
            },
        )

        self.assertEqual(response.status_code, 302)
        campaign.refresh_from_db()
        suggestion.refresh_from_db()
        created_item = Item.objects.filter(campaign=campaign).first()

        self.assertIsNotNone(created_item)
        self.assertEqual(created_item.category.name, 'Woodworking')
        self.assertEqual(campaign.category.name, 'Woodworking')
        self.assertEqual(suggestion.category.name, 'Woodworking')