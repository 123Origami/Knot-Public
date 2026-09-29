"""
Management command to debug payment issues
Usage: python manage.py debug_payments [--booking-id <id>] [--status <status>]
"""
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.bookings.models import Booking
from apps.payments.models import Transaction
from apps.campaigns.payhero import payhero


class Command(BaseCommand):
    help = 'Debug payment issues by checking PayHero status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--booking-id',
            type=int,
            help='Specific booking ID to debug'
        )
        parser.add_argument(
            '--status',
            default='pending',
            help='Filter bookings by status (default: pending). Options: pending, paid, failed'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit number of bookings to check (default: 10)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 Payment Debugging Tool\n'))

        if options['booking_id']:
            self.debug_single_booking(options['booking_id'])
        else:
            self.debug_multiple_bookings(options['status'], options['limit'])

    def debug_single_booking(self, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
            self.stdout.write(self.style.SUCCESS(f'\n📋 Booking #{booking.id}'))
            self.stdout.write(f'   Item: {booking.item.name}')
            self.stdout.write(f'   Borrower: {booking.borrower.email}')
            self.stdout.write(f'   Status: {booking.status}')
            self.stdout.write(f'   Payment Status: {booking.payment_status}')
            self.stdout.write(f'   Total Fee: {booking.total_fee}')
            
            transaction = Transaction.objects.filter(
                booking=booking,
                transaction_type='booking_fee'
            ).order_by('-created_at').first()

            if not transaction:
                self.stdout.write(self.style.WARNING('\n   ⚠️ No transaction found!'))
                return

            self.stdout.write(self.style.SUCCESS(f'\n   💳 Transaction #{transaction.id}'))
            self.stdout.write(f'      Status: {transaction.status}')
            self.stdout.write(f'      Amount: {transaction.amount}')
            self.stdout.write(f'      Created: {transaction.created_at}')
            self.stdout.write(f'      References in DB:')
            self.stdout.write(f'        - payhero_reference: {transaction.payhero_reference}')
            self.stdout.write(f'        - payhero_checkout_id: {transaction.payhero_checkout_id}')
            self.stdout.write(f'        - transaction_id: {transaction.transaction_id}')
            self.stdout.write(f'        - mpesa_receipt: {transaction.mpesa_receipt}')

            self.check_payhero_status(transaction)

        except Booking.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Booking #{booking_id} not found'))

    def debug_multiple_bookings(self, status_filter, limit):
        bookings = Booking.objects.all()
        
        if status_filter == 'pending':
            bookings = bookings.filter(status__in=['pending', 'awaiting_payment'])
        elif status_filter == 'paid':
            bookings = bookings.filter(status='paid')
        elif status_filter == 'failed':
            bookings = bookings.exclude(status='paid')

        bookings = bookings.order_by('-created_at')[:limit]

        self.stdout.write(self.style.SUCCESS(f'\n📊 Checking {bookings.count()} bookings...\n'))

        stuck_payments = 0
        all_transactions = []
        
        for booking in bookings:
            transaction = Transaction.objects.filter(
                booking=booking,
                transaction_type='booking_fee'
            ).order_by('-created_at').first()

            if not transaction:
                continue

            # Check if payment is stuck (created more than 5 minutes ago but still pending)
            time_diff = timezone.now() - transaction.created_at
            is_stuck = (transaction.status == 'pending' and time_diff.total_seconds() > 300)

            all_transactions.append({
                'booking_id': booking.id,
                'transaction_id': transaction.id,
                'status': transaction.status,
                'created': transaction.created_at,
                'age_seconds': int(time_diff.total_seconds()),
                'is_stuck': is_stuck,
                'references': {
                    'payhero_reference': transaction.payhero_reference,
                    'payhero_checkout_id': transaction.payhero_checkout_id,
                    'transaction_id': transaction.transaction_id,
                }
            })

            if is_stuck:
                stuck_payments += 1
                self.stdout.write(self.style.WARNING(f'\n⏱️  STUCK: Booking #{booking.id}'))
                self.stdout.write(f'   Status: {transaction.status}')
                self.stdout.write(f'   Created {time_diff.seconds} seconds ago')
                self.stdout.write(f'   References:')
                self.stdout.write(f'     - payhero_reference: {transaction.payhero_reference}')
                self.stdout.write(f'     - payhero_checkout_id: {transaction.payhero_checkout_id}')
                self.stdout.write(f'     - transaction_id: {transaction.transaction_id}')
                self.check_payhero_status(transaction)

        if stuck_payments == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No stuck payments found!'))
        else:
            self.stdout.write(self.style.ERROR(f'\n❌ Found {stuck_payments} stuck payments'))
        
        # Print summary as table
        if all_transactions:
            self.stdout.write(self.style.SUCCESS('\n📊 Summary of All Transactions:'))
            self.stdout.write(f"\n{'Booking':<12} {'Txn':<8} {'Status':<12} {'Age':<12} {'Stuck':<6}")
            self.stdout.write("-" * 60)
            for t in all_transactions:
                stuck_mark = '🔴' if t['is_stuck'] else '✓'
                self.stdout.write(
                    f"BKG-{t['booking_id']:<7} {t['transaction_id']:<8} "
                    f"{t['status']:<12} {t['age_seconds']}s{'':<7} {stuck_mark:<6}"
                )

    def check_payhero_status(self, transaction):
        """Check PayHero status for a transaction"""
        candidate_references = [
            transaction.payhero_reference,
            transaction.payhero_checkout_id,
            transaction.transaction_id,
        ]

        self.stdout.write(f'\n   🔄 Checking PayHero with {len([r for r in candidate_references if r])} references:')
        
        found_success = False
        for ref in candidate_references:
            if not ref:
                self.stdout.write(f'      ⊘ (empty reference)')
                continue

            self.stdout.write(f'\n      Testing: {ref}')
            
            try:
                response = payhero.check_transaction_status(ref)
                
                # Check if response indicates success
                status_value = str(response.get('status', '')).lower().strip()
                result_code = str(response.get('ResultCode', '')).strip()
                result_value = str(response.get('Result', response.get('result', ''))).lower().strip()
                
                is_success = (
                    status_value in ['completed', 'success', 'paid', 'successful'] or 
                    result_code in ['0', '00', '000'] or
                    result_value in ['completed', 'success', 'paid', 'successful']
                )
                
                if is_success:
                    self.stdout.write(self.style.SUCCESS(f'      ✅ SUCCESS! Status={status_value}'))
                    found_success = True
                else:
                    if 'error_code' in response and response['error_code'] == 'NOT_FOUND':
                        self.stdout.write(f'      ❌ Not found on PayHero')
                    else:
                        self.stdout.write(f'      ⏳ Pending - {json.dumps(response, indent=18)[:100]}...')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'      ❌ Error: {str(e)[:50]}'))
        
        if found_success:
            self.stdout.write(self.style.SUCCESS(f'      💡 Payment succeeded! Click "Check Again" in app to sync.'))

