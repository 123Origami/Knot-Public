from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.campaigns.models import Campaign
from apps.core.models import Notification

from .models import Category, ItemSuggestion


User = get_user_model()


class SuggestionVoteRulesTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='voter',
            email='voter@example.com',
            password='testpass123',
        )
        self.category = Category.objects.create(name='Technology', slug='technology')

    def test_pending_suggestion_cannot_be_voted_on(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.user,
            name='Pending Projector',
            description='A projector for shared workshops.',
            estimated_cost=5000,
            category=self.category,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/items/suggestions/{suggestion.id}/vote/')

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error'], 'This suggestion is not open for voting until it is approved by an admin.')
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.votes, 0)

    def test_non_pending_suggestion_can_be_voted_on(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.user,
            name='Approved Projector',
            description='A projector for shared workshops.',
            estimated_cost=5000,
            category=self.category,
            status='campaign_created',
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/items/suggestions/{suggestion.id}/vote/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['voted'])
        self.assertEqual(response.data['votes'], 1)


class SuggestionApproveEditTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123',
        )
        self.suggested_by = User.objects.create_user(
            username='requester',
            email='requester@example.com',
            password='testpass123',
        )
        self.category = Category.objects.create(name='Technology', slug='technology')

    def test_approve_endpoint_applies_edited_goal_fields(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.suggested_by,
            name='Old Projector',
            description='Old description.',
            estimated_cost=2500,
            category=self.category,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/items/suggestions/{suggestion.id}/approve/',
            {
                'name': 'Community Projector',
                'description': 'A projector for workshops and events.',
                'category': str(self.category.id),
                'estimated_cost': '4200',
                'target_amount': '5000',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        campaign = Campaign.objects.get(suggested_item=suggestion)

        self.assertEqual(suggestion.name, 'Community Projector')
        self.assertEqual(suggestion.description, 'A projector for workshops and events.')
        self.assertEqual(str(suggestion.estimated_cost), '4200.00')
        self.assertEqual(suggestion.status, 'campaign_created')
        self.assertEqual(campaign.title, 'Community Projector')
        self.assertEqual(campaign.description, 'A projector for workshops and events.')
        self.assertEqual(str(campaign.target_amount), '5000.00')

        notification = Notification.objects.filter(user=self.suggested_by).order_by('-created_at').first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.title, 'Goal Published: Community Projector')
        self.assertIn('Your community suggestion is now live', notification.message)
        self.assertNotIn('localhost', notification.message.lower())
        self.assertEqual(notification.related_url, reverse('campaign_detail', args=[campaign.id]))

    def test_approve_endpoint_can_create_new_category(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.suggested_by,
            name='Community Camera',
            description='Initial description.',
            estimated_cost=1500,
            category=self.category,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/items/suggestions/{suggestion.id}/approve/',
            {
                'name': 'Community Camera Kit',
                'description': 'Updated description.',
                'estimated_cost': '2200',
                'target_amount': '3000',
                'new_category_name': 'Media Lab',
            },
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        suggestion.refresh_from_db()
        campaign = Campaign.objects.get(suggested_item=suggestion)
        self.assertEqual(suggestion.category.name, 'Media Lab')
        self.assertEqual(campaign.category.name, 'Media Lab')

    def test_approve_endpoint_can_update_campaign_photo(self):
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.suggested_by,
            name='Portable Speaker',
            description='Initial description.',
            estimated_cost=1200,
            category=self.category,
        )

        image_file = SimpleUploadedFile('goal-photo.jpg', b'fake-image-bytes', content_type='image/jpeg')

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/items/suggestions/{suggestion.id}/approve/',
            {
                'name': 'Portable Speaker Set',
                'description': 'Updated description.',
                'category': str(self.category.id),
                'estimated_cost': '1800',
                'target_amount': '2500',
                'image': image_file,
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        campaign = Campaign.objects.get(suggested_item=suggestion)
        self.assertTrue(bool(campaign.image))
        self.assertIn('campaign_images/', campaign.image.name)
        self.assertTrue(bool(response.data.get('campaign_image_url')))

    def test_approve_uses_member_suggestion_photo_when_admin_does_not_replace(self):
        suggestion_image = SimpleUploadedFile('suggestion-photo.jpg', b'fake-suggestion-image', content_type='image/jpeg')
        suggestion = ItemSuggestion.objects.create(
            suggested_by=self.suggested_by,
            name='Community Tent',
            description='Initial description.',
            estimated_cost=3200,
            category=self.category,
            image=suggestion_image,
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            f'/api/items/suggestions/{suggestion.id}/approve/',
            {
                'name': 'Community Tent Kit',
                'description': 'Updated description.',
                'category': str(self.category.id),
                'estimated_cost': '3500',
                'target_amount': '4000',
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, 200)
        campaign = Campaign.objects.get(suggested_item=suggestion)
        self.assertTrue(bool(campaign.image))
        self.assertIn('suggestion_images/', campaign.image.name)