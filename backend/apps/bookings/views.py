from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Booking, BookingHistory
from .serializers import (
    BookingSerializer, BookingDetailSerializer, BookingCreateSerializer,
    BookingActionSerializer, BookingHistorySerializer
)

from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from .models import Booking
from apps.items.models import Item
from django.utils import timezone
from datetime import datetime, timedelta
from urllib.parse import urlparse
import re
import json
import uuid
from apps.campaigns.payhero import payhero
from apps.payments.models import Transaction
from apps.core.models import Notification, SiteSettings
from .services import sync_overdue_bookings_for_user, get_unreturned_overdue_bookings_for_borrower

IMAGE_ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
BOOKING_ID_MAX_SIZE_BYTES = 5 * 1024 * 1024


def _file_extension(filename):
    if not filename or '.' not in filename:
        return ''
    return f".{filename.rsplit('.', 1)[-1].lower()}"


def _validate_booking_id_photo(photo_file):
    if not photo_file:
        return 'Please upload a clear photo of your ID to submit this booking request.'

    ext = _file_extension(getattr(photo_file, 'name', ''))
    if ext not in IMAGE_ALLOWED_EXTENSIONS:
        return 'ID photo must be JPG, PNG, or WEBP.'

    if getattr(photo_file, 'size', 0) > BOOKING_ID_MAX_SIZE_BYTES:
        return 'ID photo must be 5MB or smaller.'

    return None

class BookingViewSet(viewsets.ModelViewSet):
    """ViewSet for bookings"""
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    lookup_field = 'booking_id'
    
    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['approve', 'decline', 'checkout', 'checkin']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BookingDetailSerializer
        elif self.action == 'create':
            return BookingCreateSerializer
        elif self.action in ['approve', 'decline', 'cancel']:
            return BookingActionSerializer
        return BookingSerializer
    
    def get_queryset(self):
        user = self.request.user

        if user.is_authenticated:
            sync_overdue_bookings_for_user(user)
        
        if user.is_authenticated:
            # Users can see their own bookings
            queryset = Booking.objects.filter(
                Q(borrower=user) | Q(item__steward=user)
            )
        else:
            queryset = Booking.objects.none()
        
        # Filter by status
        status = self.request.query_params.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by role
        role = self.request.query_params.get('role', None)
        if role == 'borrower':
            queryset = queryset.filter(borrower=user)
        elif role == 'steward':
            queryset = queryset.filter(item__steward=user)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        booking = serializer.save(borrower=self.request.user)
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            action='created',
            performed_by=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, booking_id=None):
        """Approve a booking request"""
        booking = self.get_object()
        
        # Check permission
        if booking.item.steward != request.user:
            return Response(
                {'error': 'Only the item steward can approve bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'pending':
            return Response(
                {'error': f'Cannot approve booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        booking.status = 'approved'
        booking.steward = request.user
        booking.approved_at = timezone.now()
        booking.pickup_date = serializer.validated_data.get('pickup_date')
        booking.pickup_location = serializer.validated_data.get('pickup_location', booking.item.location_details)
        booking.pickup_time = serializer.validated_data.get('pickup_time')
        booking.notes = serializer.validated_data.get('notes', '')
        booking.save()
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            action='approved',
            performed_by=request.user,
            notes=serializer.validated_data.get('notes', '')
        )
        
        return Response({'status': 'booking approved'})
    
    @action(detail=True, methods=['post'])
    def decline(self, request, booking_id=None):
        """Decline a booking request"""
        booking = self.get_object()
        
        # Check permission
        if booking.item.steward != request.user:
            return Response(
                {'error': 'Only the item steward can decline bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'pending':
            return Response(
                {'error': f'Cannot decline booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        booking.status = 'declined'
        booking.steward = request.user
        booking.notes = serializer.validated_data.get('notes', '')
        booking.save()
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            action='declined',
            performed_by=request.user,
            notes=serializer.validated_data.get('notes', '')
        )
        
        return Response({'status': 'booking declined'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, booking_id=None):
        """Cancel a booking"""
        booking = self.get_object()
        
        # Check permission
        if booking.borrower != request.user and booking.item.steward != request.user:
            return Response(
                {'error': 'Only the borrower or steward can cancel bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status not in ['pending', 'approved']:
            return Response(
                {'error': f'Cannot cancel booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        booking.status = 'cancelled'
        booking.notes = serializer.validated_data.get('notes', '')
        booking.save()
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            action='cancelled',
            performed_by=request.user,
            notes=serializer.validated_data.get('notes', '')
        )
        
        return Response({'status': 'booking cancelled'})
    
    @action(detail=True, methods=['post'])
    def checkout(self, request, booking_id=None):
        """Check out item (start rental)"""
        booking = self.get_object()
        
        # Check permission
        if booking.item.steward != request.user:
            return Response(
                {'error': 'Only the item steward can check out items'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'paid':
            return Response(
                {'error': f'Cannot check out booking with status {booking.status}. Payment must be completed first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.check_out()
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            action='checked_out',
            performed_by=request.user
        )
        
        return Response({'status': 'item checked out'})
    
    @action(detail=True, methods=['post'])
    def checkin(self, request, booking_id=None):
        """Check in item (return)"""
        booking = self.get_object()
        
        # Check permission
        if booking.item.steward != request.user:
            return Response(
                {'error': 'Only the item steward can check in items'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'active':
            return Response(
                {'error': f'Cannot check in booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.check_in()
        
        # Create history entry
        BookingHistory.objects.create(
            booking=booking,
            action='returned',
            performed_by=request.user
        )
        
        return Response({'status': 'item returned'})
    
    @action(detail=True, methods=['post'])
    def pay(self, request, booking_id=None):
        """Initiate booking payment via PayHero STK push"""
        if not SiteSettings.payments_enabled():
            return Response({
                'error': 'Payments are disabled on this demo deployment. The M-Pesa/PayHero booking payment flow is fully implemented in the code, but live transactions are turned off here.'
            }, status=status.HTTP_403_FORBIDDEN)

        booking = self.get_object()

        # Check permission - only borrower can pay
        if booking.borrower != request.user:
            return Response(
                {'error': 'Only the borrower can make payment'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'approved':
            return Response(
                {'error': f'Cannot pay for booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        phone_number = request.data.get('phone_number') or getattr(request.user, 'phone_number', None)
        if not phone_number:
            return Response({'error': 'Phone number is required for payment.'}, status=status.HTTP_400_BAD_REQUEST)

        if not booking.total_fee:
            days = (booking.end_date - booking.start_date).days + 1
            daily_rate = booking.item.daily_rate or 0
            booking.total_fee = daily_rate * days
            booking.save(update_fields=['total_fee'])

        external_reference = f"BKG-{booking.id}-{uuid.uuid4().hex[:8].upper()}"
        transaction = Transaction.objects.create(
            transaction_type='booking_fee',
            payment_method='mpesa',
            amount=booking.total_fee,
            phone_number=str(phone_number),
            user=request.user,
            booking=booking,
            payhero_reference=external_reference,
            description=f"Booking payment for {booking.item.name}",
            status='pending',
            metadata={
                'booking_id': booking.id,
                'booking_code': booking.booking_id,
                'item_name': booking.item.name,
            },
        )

        payment_result = payhero.initiate_payment(
            amount=booking.total_fee,
            phone_number=str(phone_number),
            external_reference=external_reference,
            description=f"Booking payment for {booking.item.name}",
            callback_url=getattr(settings, 'BOOKING_PAYHERO_CALLBACK_URL', ''),
        )

        if 'error' in payment_result:
            transaction.status = 'failed'
            transaction.save(update_fields=['status'])
            return Response(
                {
                    'error': payment_result.get('error', 'Payment initiation failed'),
                    'details': payment_result.get('details', ''),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extract all possible transaction IDs from PayHero response
        # PayHero v2 might return different field names
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📨 PayHero Response Keys: {list(payment_result.keys())}")
        logger.info(f"📨 Full Response: {json.dumps(payment_result, indent=2)}")
        
        checkout_id = (
            payment_result.get('CheckoutRequestID') or 
            payment_result.get('checkout_request_id') or
            payment_result.get('transaction_id') or
            payment_result.get('TransactionID') or
            payment_result.get('id') or
            payment_result.get('request_id')
        )
        
        # Also try to capture the actual PayHero reference/ID for verification
        payhero_txn_id = (
            payment_result.get('id') or
            payment_result.get('transaction_id') or
            payment_result.get('TransactionID') or
            payment_result.get('reference') or
            checkout_id
        )
        
        logger.info(f"✅ Extracted checkout_id: {checkout_id}")
        logger.info(f"✅ Extracted payhero_txn_id: {payhero_txn_id}")
        
        if checkout_id:
            transaction.payhero_checkout_id = checkout_id
            transaction.save(update_fields=['payhero_checkout_id'])
        
        # Store additional reference for verification attempts
        if payhero_txn_id and payhero_txn_id != checkout_id:
            if not transaction.transaction_id or transaction.transaction_id.startswith('BKF-'):
                # Update transaction_id if it's just our internal format
                transaction.transaction_id = payhero_txn_id
                transaction.save(update_fields=['transaction_id'])
                logger.info(f"✅ Stored PayHero transaction_id: {payhero_txn_id}")

        return Response(
            {
                'status': 'payment_pending',
                'message': 'STK push sent. Complete payment on your phone.',
                'checkout_request_id': checkout_id,
                'transaction_id': transaction.transaction_id,
            }
        )
    
    @action(detail=True, methods=['get'])
    def history(self, request, booking_id=None):
        """Get booking history"""
        booking = self.get_object()
        history = booking.history.all()
        serializer = BookingHistorySerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def verify_payment(self, request, booking_id=None):
        """Manually verify booking payment status from PayHero and update booking if completed."""
        import logging
        logger = logging.getLogger(__name__)
        
        booking = self.get_object()
        logger.info(f"🔏 Verifying payment for booking {booking.id}")

        if booking.borrower != request.user:
            return Response(
                {'error': 'Only the borrower can verify payment for this booking.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.status == 'paid' or booking.payment_status == 'paid':
            logger.info(f"✅ Booking {booking.id} already marked as paid")
            return Response({'status': 'paid', 'message': 'Booking already marked as paid.'})

        transaction = Transaction.objects.filter(
            booking=booking,
            transaction_type='booking_fee',
        ).order_by('-created_at').first()

        if not transaction:
            logger.warning(f"⚠️ No booking payment transaction found for booking {booking.id}")
            return Response({'error': 'No booking payment transaction found.'}, status=status.HTTP_404_NOT_FOUND)

        logger.info(f"📊 Transaction status in DB: {transaction.status}")
        logger.info(f"📋 Transaction references - payhero_reference: {transaction.payhero_reference}, checkout_id: {transaction.payhero_checkout_id}, transaction_id: {transaction.transaction_id}")

        # Local reconciliation: transaction may already be completed even if booking state wasn't updated.
        if transaction.status == 'completed':
            logger.info(f"✅ Transaction {transaction.id} already completed in DB, updating booking")
            booking.status = 'paid'
            booking.payment_status = 'paid'
            if not booking.payment_date:
                booking.payment_date = timezone.now()
            booking.save(update_fields=['status', 'payment_status', 'payment_date'])

            return Response({'status': 'paid', 'message': 'Payment already completed and booking updated.'})

        # Some providers return status by either external reference or checkout request id.
        candidate_references = [
            transaction.payhero_reference,
            transaction.payhero_checkout_id,
            transaction.transaction_id,
        ]

        verification = {'status': 'pending'}
        for idx, candidate_reference in enumerate(candidate_references):
            if not candidate_reference:
                logger.debug(f"Skipping empty reference at index {idx}")
                continue
            logger.info(f"🔄 Attempt {idx + 1}: Checking reference: {candidate_reference}")
            attempt = payhero.check_transaction_status(candidate_reference)
            logger.info(f"📨 Response from PayHero: {json.dumps(attempt, indent=2)}")
            attempt_text = json.dumps(attempt).lower()
            if 'not found' in attempt_text:
                logger.warning(f"⚠️ Reference {candidate_reference} not found on PayHero")
                continue
            verification = attempt
            logger.info(f"✔️ Using verification result from reference: {candidate_reference}")
            break

        verification_text = json.dumps(verification).lower()
        status_value = str(verification.get('status', '')).lower().strip()
        result_value = str(verification.get('Result', verification.get('result', ''))).lower().strip()
        result_code = str(verification.get('ResultCode', '')).strip()
        
        logger.info(f"📊 Verification analysis:")
        logger.info(f"  - status_value: '{status_value}'")
        logger.info(f"  - result_value: '{result_value}'")
        logger.info(f"  - result_code: '{result_code}'")
        
        verified_success = (
            result_code in ['0', '00', '000']
            or status_value in ['completed', 'success', 'paid', 'successful']
            or result_value in ['completed', 'success', 'paid', 'successful']
            or 'completed' in verification_text
            or 'success' in verification_text
            or 'paid' in verification_text
        )

        logger.info(f"🔎 Verification result: {'SUCCESS' if verified_success else 'PENDING'}")

        if verified_success:
            logger.info(f"✅ Payment verified! Updating transaction and booking")
            if transaction.status != 'completed':
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.save(update_fields=['status', 'completed_at'])

            booking.status = 'paid'
            booking.payment_status = 'paid'
            booking.payment_date = timezone.now()
            booking.save(update_fields=['status', 'payment_status', 'payment_date'])

            BookingHistory.objects.create(
                booking=booking,
                action='paid',
                performed_by=request.user,
                notes='Payment verified from PayHero status API.'
            )

            Notification.objects.create(
                user=booking.borrower,
                notification_type='payment_received',
                title='Booking Payment Confirmed',
                message=f'Your payment for {booking.item.name} has been confirmed.',
                related_url='/dashboard/'
            )

            return Response({'status': 'paid', 'message': 'Payment verified and booking updated.'})

        logger.warning(f"⚠️ Payment still pending. Full response: {json.dumps(verification, indent=2)}")
        return Response(
            {
                'status': 'pending',
                'message': 'Payment not confirmed yet. Please wait a moment and try again.',
                'verification': verification,
            },
            status=status.HTTP_200_OK,
        )




class CreateBookingView(APIView):
    """API view for creating bookings"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """Create a new booking request"""
        overdue_qs = get_unreturned_overdue_bookings_for_borrower(request.user)
        if overdue_qs.exists():
            return Response(
                {
                    'error': 'You have overdue items that have not been returned. Return them before booking another item.',
                    'overdue_count': overdue_qs.count(),
                },
                status=400,
            )

        item_id = request.data.get('item_id') or request.data.get('itemId') or request.data.get('item')
        start_date_str = request.data.get('start_date') or request.data.get('startDate')
        end_date_str = request.data.get('end_date') or request.data.get('endDate')
        purpose = request.data.get('purpose', '')
        borrower_id_photo = request.FILES.get('borrower_id_photo') or request.data.get('borrower_id_photo')

        id_photo_error = _validate_booking_id_photo(borrower_id_photo)
        if id_photo_error:
            return Response({'error': id_photo_error}, status=400)

        # Fallback: infer item id from the referring page URL.
        # Handles both /book-item/<id>/ and /items/detail/<slug>/ pages.
        if not item_id:
            referer = request.headers.get('Referer', '') or request.META.get('HTTP_REFERER', '')
            if referer:
                parsed_path = urlparse(referer).path

                id_match = re.search(r'/book-item/(\d+)/', parsed_path)
                if id_match:
                    item_id = id_match.group(1)
                else:
                    slug_match = re.search(r'/items/detail/([^/]+)/', parsed_path)
                    if slug_match:
                        slug = slug_match.group(1)
                        item = Item.objects.filter(slug=slug).only('id').first()
                        if item:
                            item_id = item.id

        missing_fields = []
        if not item_id:
            missing_fields.append('item_id')
        if not start_date_str:
            missing_fields.append('start_date')
        if not end_date_str:
            missing_fields.append('end_date')

        if missing_fields:
            return Response(
                {
                    'error': f"Missing required fields: {', '.join(missing_fields)}",
                    'missing_fields': missing_fields,
                    'received_keys': list(request.data.keys()),
                },
                status=400,
            )

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        today = timezone.localdate()
        if start_date < today or end_date < today:
            return Response({'error': 'Past dates cannot be booked.'}, status=400)

        if end_date < start_date:
            return Response({'error': 'End date cannot be before start date.'}, status=400)

        item = get_object_or_404(Item, id=item_id)

        blocking_statuses = ['pending', 'approved', 'paid', 'active', 'overdue']
        has_blocking_booking = Booking.objects.filter(
            item=item,
            status__in=blocking_statuses,
        ).exists()

        # Recover stale item status after return flows where booking closed but item remained borrowed.
        if item.status == 'borrowed' and not has_blocking_booking:
            item.status = 'available'
            item.save(update_fields=['status'])

        booking_days = (end_date - start_date).days + 1

        if booking_days > item.max_borrow_days:
            return Response(
                {
                    'error': f'Booking exceeds maximum allowed duration of {item.max_borrow_days} days.',
                    'max_borrow_days': item.max_borrow_days,
                    'requested_days': booking_days,
                },
                status=400,
            )

        # Check for overlapping bookings (consider buffer after existing bookings)
        BUFFER_DAYS = 3
        offset = timedelta(days=(BUFFER_DAYS - 1))
        overlapping = Booking.objects.filter(
            item=item,
            status__in=blocking_statuses,
            start_date__lte=end_date,
            end_date__gte=(start_date - offset)
        ).exists()

        if overlapping:
            return Response({'error': 'Selected dates are not available'}, status=400)

        # Create booking
        booking = Booking.objects.create(
            item=item,
            borrower=request.user,
            start_date=start_date,
            end_date=end_date,
            purpose=purpose,
            borrower_id_photo=borrower_id_photo,
            status='pending'
        )

        return Response({
            'message': 'Booking request created',
            'booking_id': booking.booking_id,
            'status': booking.status
        }, status=201)


@csrf_exempt
def booking_payment_callback(request):
    """PayHero callback for booking payments"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST.dict()
        response_data = data.get('response', data)

        external_reference = (
            response_data.get('ExternalReference')
            or response_data.get('external_reference')
            or response_data.get('reference')
            or response_data.get('CheckoutRequestID')
            or response_data.get('checkout_request_id')
            or response_data.get('transaction_id')
        )
        result_code = response_data.get('ResultCode', response_data.get('result_code'))
        result_desc = response_data.get('ResultDesc')
        mpesa_receipt = response_data.get('MpesaReceiptNumber')
        status_text = str(response_data.get('status', response_data.get('Status', ''))).lower()

        if not external_reference:
            return JsonResponse({'error': 'No transaction reference'}, status=400)

        transaction = Transaction.objects.filter(
            transaction_type='booking_fee'
        ).filter(
            Q(payhero_reference=external_reference)
            | Q(payhero_checkout_id=external_reference)
            | Q(transaction_id=external_reference)
        ).first()
        if not transaction:
            return JsonResponse({'error': 'Transaction not found'}, status=404)

        booking = transaction.booking
        if not booking:
            return JsonResponse({'error': 'Booking not linked to transaction'}, status=400)

        try:
            normalized_result_code = int(str(result_code).strip())
        except (TypeError, ValueError):
            normalized_result_code = None

        is_success = normalized_result_code == 0 or status_text in ['success', 'successful', 'paid', 'completed']

        if is_success:
            transaction.status = 'completed'
            if not transaction.completed_at:
                transaction.completed_at = timezone.now()
            if mpesa_receipt:
                transaction.mpesa_receipt = mpesa_receipt
            transaction.save(update_fields=['status', 'completed_at', 'mpesa_receipt'])

            booking.status = 'paid'
            booking.payment_status = 'paid'
            if not booking.payment_date:
                booking.payment_date = timezone.now()
            booking.save(update_fields=['status', 'payment_status', 'payment_date'])

            BookingHistory.objects.create(
                booking=booking,
                action='paid',
                performed_by=booking.borrower,
                notes=f'Payment completed via PayHero. Receipt: {mpesa_receipt or "N/A"}'
            )

            Notification.objects.create(
                user=booking.borrower,
                notification_type='payment_received',
                title='Booking Payment Successful',
                message=f'Your payment for {booking.item.name} was successful. You can now pick up the item.',
                related_url='/dashboard/'
            )
        else:
            transaction.status = 'failed'
            transaction.save(update_fields=['status'])

            Notification.objects.create(
                user=booking.borrower,
                notification_type='system',
                title='Booking Payment Failed',
                message=f'Payment for {booking.item.name} failed: {result_desc or "Unknown error"}. Please try again.',
                related_url='/dashboard/'
            )

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)