"""
Management command to add a sample low-cost item for borrowing
Usage: python manage.py add_sample_item
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from decimal import Decimal
from apps.items.models import Item, Category
from apps.accounts.models import CustomUser


class Command(BaseCommand):
    help = 'Add a sample low-cost item (10 KSH/day) for testing borrowing'

    def handle(self, *args, **options):
        # Get or create a default category
        category, created = Category.objects.get_or_create(
            name='Tools & Equipment',
            defaults={'slug': 'tools-equipment'}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created category: {category.name}'))
        
        # Get a steward (use first admin or available user)
        steward = CustomUser.objects.filter(is_staff=True).first()
        if not steward:
            steward = CustomUser.objects.first()
            if not steward:
                self.stdout.write(self.style.ERROR('❌ No users found. Create a user first.'))
                return
        
        self.stdout.write(f'📝 Using steward: {steward.email}')
        
        # Create the item
        item_name = 'DIY Drill Kit'
        slug = slugify(item_name)
        
        # Check if item already exists
        if Item.objects.filter(slug=slug).exists():
            item = Item.objects.get(slug=slug)
            self.stdout.write(self.style.WARNING(f'⚠️  Item already exists: {item.name} (ID: {item.id})'))
            self.print_item_details(item)
            return
        
        item = Item.objects.create(
            name=item_name,
            slug=slug,
            description='Professional-grade cordless drill kit with battery and charger. Perfect for DIY projects, home repairs, and light construction work. Includes drill bits, impact driver bits, and hard carrying case.',
            category=category,
            steward=steward,
            condition='good',
            status='available',
            location_details='Nairobi CBD - Available for pickup Monday to Friday 9 AM - 5 PM',
            daily_rate=Decimal('10.00'),  # 10 KSH per day
            deposit_amount=Decimal('10.00'),  # 10 KSH deposit
            max_borrow_days=7,  # Max 7 days
            total_bookings=0,
        )
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully created item: {item.name}'))
        self.print_item_details(item)
    
    def print_item_details(self, item):
        """Print item details in a formatted way"""
        self.stdout.write(f'\n📦 Item Details:')
        self.stdout.write(f'   ID: {item.id}')
        self.stdout.write(f'   Name: {item.name}')
        self.stdout.write(f'   Slug: {item.slug}')
        self.stdout.write(f'   Daily Rate: {item.daily_rate} KSH')
        self.stdout.write(f'   Deposit: {item.deposit_amount} KSH')
        self.stdout.write(f'   Max Borrow Days: {item.max_borrow_days}')
        self.stdout.write(f'   Category: {item.category.name}')
        self.stdout.write(f'   Steward: {item.steward.email}')
        self.stdout.write(f'   Condition: {item.condition}')
        self.stdout.write(f'   Status: {item.status}')
        self.stdout.write(f'   Location: {item.location_details}')
        self.stdout.write(f'\n💰 Pricing for 1 day: {item.daily_rate} KSH + {item.deposit_amount} KSH deposit = {item.daily_rate + item.deposit_amount} KSH total')
        self.stdout.write(f'\n🔗 Access this item at: /dashboard/#item/{item.id}')
