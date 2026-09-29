import json
import hmac
import hashlib
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Transaction, Contribution, Payout
from .serializers import (
    TransactionSerializer, TransactionDetailSerializer,
    MpesaPaymentSerializer, CardPaymentSerializer,
    ContributionSerializer, PayoutSerializer, PayoutInitiateSerializer
)
from .payhero_client import PayheroClient
from apps.campaigns.models import Campaign
from apps.accounts.models import CustomUser

# Initialize Payhero client
payhero = PayheroClient(sandbox=True)  # Set to False for production

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing transactions"""
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TransactionDetailSerializer
        return TransactionSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Transaction.objects.filter(user=user).order_by('-created_at')
        return Transaction.objects.none()


class ContributionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing contributions"""
    queryset = Contribution.objects.all()
    serializer_class = ContributionSerializer
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Contribution.objects.filter(user=user).order_by('-created_at')
        return Transaction.objects.none()


class InitiateMpesaPaymentView(APIView):
    """Initiate M-Pesa STK Push payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = MpesaPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        campaign = get_object_or_404(Campaign, id=data['campaign_id'])
        
        # Generate reference
        reference = f"KNOT-{campaign.id}-{request.user.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create transaction record
        transaction = Transaction.objects.create(
            transaction_type='contribution',
            status='pending',
            payment_method='mpesa',
            amount=data['amount'],
            currency='KES',
            phone_number=data['phone_number'],
            user=request.user,
            campaign=campaign,
            description=f'Contribution to {campaign.title}',
            metadata={'is_anonymous': data['is_anonymous']}
        )
        
        # Initiate STK Push
        response = payhero.stk_push(
            phone_number=data['phone_number'],
            amount=data['amount'],
            reference=reference,
            description=f"Contribution to {campaign.title}"
        )
        
        if response.get('success'):
            transaction.payhero_checkout_id = response.get('checkout_id')
            transaction.save()
            
            return Response({
                'success': True,
                'message': 'STK Push sent. Please check your phone and enter PIN.',
                'checkout_id': response.get('checkout_id'),
                'transaction_id': transaction.transaction_id
            })
        else:
            transaction.status = 'failed'
            transaction.save()
            
            return Response({
                'success': False,
                'error': response.get('message', 'Payment initiation failed')
            }, status=status.HTTP_400_BAD_REQUEST)


class InitiateCardPaymentView(APIView):
    """Initiate card payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = CardPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        campaign = get_object_or_404(Campaign, id=data['campaign_id'])
        
        # Generate reference
        reference = f"KNOT-{campaign.id}-{request.user.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create transaction record
        transaction = Transaction.objects.create(
            transaction_type='contribution',
            status='pending',
            payment_method='card',
            amount=data['amount'],
            currency='KES',
            user=request.user,
            campaign=campaign,
            description=f'Contribution to {campaign.title}',
            metadata={'is_anonymous': data['is_anonymous']}
        )
        
        # Initiate card charge
        response = payhero.charge_card(
            card_token=data['card_token'],
            amount=data['amount'],
            reference=reference,
            description=f"Contribution to {campaign.title}"
        )
        
        if response.get('success'):
            transaction.payhero_reference = response.get('reference')
            transaction.save()
            
            return Response({
                'success': True,
                'message': 'Payment processing',
                'reference': response.get('reference'),
                'transaction_id': transaction.transaction_id
            })
        else:
            transaction.status = 'failed'
            transaction.save()
            
            return Response({
                'success': False,
                'error': response.get('message', 'Payment initiation failed')
            }, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@require_POST
def payhero_webhook(request):
    """
    Handle Payhero webhook notifications
    URL: /api/payments/webhook/
    """
    # Verify signature
    signature = request.headers.get('x-payhero-signature')
    if not signature:
        return HttpResponse('Missing signature', status=401)
    
    if not payhero.verify_webhook_signature(request.body, signature):
        return HttpResponse('Invalid signature', status=401)
    
    try:
        data = json.loads(request.body)
        event = data.get('event')
        event_data = data.get('data', {})
        
        # Find transaction by reference
        reference = event_data.get('reference')
        transaction = Transaction.objects.filter(
            payhero_checkout_id=reference
        ).first() or Transaction.objects.filter(
            transaction_id=reference
        ).first()
        
        if not transaction:
            return HttpResponse('Transaction not found', status=404)
        
        if event == 'transaction.completed':
            # Payment successful
            transaction.status = 'completed'
            transaction.completed_at = timezone.now()
            transaction.payhero_reference = event_data.get('mpesa_receipt') or event_data.get('reference')
            transaction.mpesa_receipt = event_data.get('mpesa_receipt', '')
            transaction.save()
            
            # Create contribution record
            Contribution.objects.create(
                user=transaction.user,
                campaign=transaction.campaign,
                transaction=transaction,
                amount=transaction.amount,
                is_anonymous=transaction.metadata.get('is_anonymous', False)
            )
            
            # Update campaign funds
            campaign = transaction.campaign
            campaign.funds_raised += transaction.amount
            campaign.save()
            
            # Check if campaign reached target
            campaign.check_if_funded()
            
        elif event == 'transaction.failed':
            transaction.status = 'failed'
            transaction.save()
            
        elif event == 'transaction.reversed':
            transaction.status = 'refunded'
            transaction.save()
            
            # Reduce campaign funds
            campaign = transaction.campaign
            if campaign:
                campaign.funds_raised -= transaction.amount
                campaign.save()
        
        return HttpResponse('OK', status=200)
        
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)


class PaymentSuccessView(APIView):
    """Payment success page data"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        transaction_id = request.query_params.get('transaction')
        transaction = get_object_or_404(Transaction, transaction_id=transaction_id, user=request.user)
        
        return Response({
            'success': True,
            'transaction_id': transaction.transaction_id,
            'amount': transaction.amount,
            'campaign': transaction.campaign.title if transaction.campaign else None,
            'date': transaction.completed_at or transaction.created_at,
            'payment_method': transaction.payment_method
        })


class InitiatePayoutView(APIView):
    """Admin: Initiate payout to organization"""
    permission_classes = [permissions.IsAdminUser]
    
    def post(self, request):
        serializer = PayoutInitiateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        from apps.campaigns.models import Organization, Campaign
        organization = get_object_or_404(Organization, id=data['organization_id'])
        campaign = get_object_or_404(Campaign, id=data['campaign_id'])
        
        # Validate amount
        if data['amount'] > campaign.funds_raised:
            return Response(
                {'error': 'Payout amount exceeds funds raised'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payout record
        payout = Payout.objects.create(
            organization=organization,
            campaign=campaign,
            amount=data['amount'],
            currency='KES',
            status='pending',
            bank_name=organization.bank_name,
            account_name=organization.account_name,
            account_number_encrypted=organization.account_number_encrypted,
            bank_code=organization.bank_code
        )
        
        # Initiate payout via Payhero
        response = payhero.initiate_payout(
            bank_details={
                'bank_code': organization.bank_code,
                'account_number': organization.account_number_encrypted,  # Decrypt in production
                'account_name': organization.account_name
            },
            amount=data['amount'],
            reference=payout.payout_id
        )
        
        if response.get('success'):
            payout.payhero_reference = response.get('reference')
            payout.save()
            
            return Response({
                'success': True,
                'message': 'Payout initiated successfully',
                'payout_id': payout.payout_id
            })
        else:
            payout.status = 'failed'
            payout.notes = response.get('message', 'Payout failed')
            payout.save()
            
            return Response({
                'success': False,
                'error': response.get('message', 'Payout initiation failed')
            }, status=status.HTTP_400_BAD_REQUEST)