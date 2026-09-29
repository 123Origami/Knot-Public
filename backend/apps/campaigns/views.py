from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from apps.accounts.models import CustomUser
from apps.payments.models import Contribution
from apps.items.models import Item
from apps.core.models import SiteSettings
import uuid

from .models import Campaign, Organization
from .payhero import payhero
from apps.payments.models import Transaction, Contribution

from .serializers import (
    CampaignSerializer, 
    ContributionSerializer, 
    CampaignSuggestionSerializer,
    OrganizationSerializer
)

# Simple test view
def test_ngrok(request):
    """Test if ngrok is working"""
    return JsonResponse({
        'status': 'ok',
        'message': 'ngrok is working!',
        'callback_url': getattr(settings, 'PAYHERO_CALLBACK_URL', 'Not set'),
    })

# Campaign List View
class CampaignListView(generics.ListAPIView):
    """List all active campaigns"""
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = Campaign.objects.select_related('category', 'suggested_item')

        status_filter = self.request.query_params.get('status', '').strip().lower()
        search = self.request.query_params.get('search', '').strip()
        sort = self.request.query_params.get('sort', '-created_at').strip()

        if status_filter in {'active', 'funded', 'expired', 'completed', 'cancelled', 'draft'}:
            queryset = queryset.filter(status=status_filter)
        else:
            queryset = queryset.filter(status__in=['active', 'funded', 'completed', 'expired'])

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(category__name__icontains=search)
            )

        if sort == 'popular':
            queryset = queryset.order_by('-contributor_count', '-created_at')
        elif sort == 'deadline':
            queryset = queryset.order_by('end_date')
        elif sort == 'progress':
            queryset = queryset.order_by('-funds_raised')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # Auto-cancel orphaned campaigns (campaigns with no suggestion)
        # This handles edge cases where a suggestion was deleted but campaign wasn't cancelled
        orphaned_campaigns = queryset.filter(
            suggested_item__isnull=True,
            status__in=['active', 'funded', 'expired']
        )
        if orphaned_campaigns.exists():
            orphaned_campaigns.update(status='cancelled')
            # Re-fetch queryset to exclude newly cancelled campaigns
            queryset = self.get_queryset()
        
        data = []
        for campaign in queryset:
            data.append({
                'id': campaign.id,
                'title': campaign.title,
                'slug': campaign.slug,
                'description': campaign.description,
                'image_url': campaign.image.url if campaign.image else '',
                'target_amount': float(campaign.target_amount),
                'funds_raised': float(campaign.funds_raised),
                'progress_percentage': campaign.get_progress_percentage(),
                'days_remaining': campaign.days_remaining(),
                'status': campaign.status,
                'created_at': campaign.created_at,
                'contributor_count': campaign.contributor_count,
            })
        return Response({'results': data})


def _is_admin_user(user: CustomUser):
    return bool(
        user.is_authenticated and (
            user.is_superuser or user.is_staff or getattr(user, 'is_admin_approved', False)
        )
    )


class CampaignPulloutView(APIView):
    """Mark funded goal as pulled out by admin for tracking."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, campaign_id):
        if not _is_admin_user(request.user):
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        campaign = get_object_or_404(Campaign, id=campaign_id)

        if campaign.status not in {'funded', 'completed'}:
            return Response(
                {'error': 'Goal pullout can only be recorded for funded/completed campaigns.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign.funds_pulled_out = True
        campaign.pulled_out_at = timezone.now()
        campaign.pulled_out_by = request.user
        campaign.save(update_fields=['funds_pulled_out', 'pulled_out_at', 'pulled_out_by', 'updated_at'])

        if campaign.status == 'funded':
            campaign.status = 'completed'
            campaign.save(update_fields=['status', 'updated_at'])

        # Auto-create an item from the funded suggestion once pullout is completed.
        created_item = Item.objects.filter(campaign=campaign).first()
        item_created_now = False
        if not created_item and campaign.suggested_item:
            suggestion = campaign.suggested_item
            steward_user = request.user or campaign.created_by
            item_location = (
                campaign.host_organization.address
                if campaign.host_organization and campaign.host_organization.address
                else 'Community Hub (update pickup location in item settings)'
            )
            item_description = suggestion.description or campaign.description or f'Community-funded item from goal: {campaign.title}'

            created_item = Item.objects.create(
                name=suggestion.name,
                description=item_description,
                category=campaign.category or suggestion.category,
                steward=steward_user,
                host_organization=campaign.host_organization,
                campaign=campaign,
                condition='new',
                status='available',
                location_details=item_location,
                daily_rate=None,
                deposit_amount=None,
                max_borrow_days=14,
            )
            item_created_now = True

        return Response({
            'message': 'Goal pullout recorded successfully.',
            'campaign_id': campaign.id,
            'funds_pulled_out': campaign.funds_pulled_out,
            'status': campaign.status,
            'item_id': created_item.id if created_item else None,
            'item_name': created_item.name if created_item else None,
            'item_created_now': item_created_now,
        })

# Campaign Statistics
class CampaignStatisticsView(APIView):
    """Get overall campaign statistics"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        # Auto-cancel orphaned campaigns (campaigns with no suggestion)
        orphaned_campaigns = Campaign.objects.filter(
            suggested_item__isnull=True,
            status__in=['active', 'funded', 'expired']
        )
        if orphaned_campaigns.exists():
            orphaned_campaigns.update(status='cancelled')
        
        active_campaigns = Campaign.objects.filter(status='active').count()
        funded_campaigns = Campaign.objects.filter(status='funded').count()
        total_raised = Campaign.objects.aggregate(Sum('funds_raised'))['funds_raised__sum'] or 0
        total_contributors = Contribution.objects.count()
        
        return Response({
            'active_campaigns': active_campaigns,
            'funded_campaigns': funded_campaigns,
            'total_raised': float(total_raised),
            'total_contributors': total_contributors
        })

# Recent Contributions
class RecentContributionsView(APIView):
    """Get recent contributions"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        contributions = Contribution.objects.filter(
            is_anonymous=False
        ).order_by('-created_at')[:10]
        
        data = []
        for contrib in contributions:
            data.append({
                'id': contrib.id,
                'user_name': contrib.user.username,
                'amount': float(contrib.amount),
                'campaign_title': contrib.campaign.title,
                'created_at': contrib.created_at,
                'is_anonymous': contrib.is_anonymous
            })
        return Response({'results': data})


class CampaignContributorsView(APIView):
    """Get recent contributors for a single campaign."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, campaign_id):
        campaign = get_object_or_404(Campaign, id=campaign_id)

        contributions = Contribution.objects.filter(campaign=campaign).select_related('user').order_by('-created_at')[:30]

        results = []
        for contrib in contributions:
            username = getattr(contrib.user, 'username', 'Member')
            results.append({
                'id': contrib.id,
                'user_name': username,
                'amount': float(contrib.amount),
                'is_anonymous': bool(contrib.is_anonymous),
                'created_at': contrib.created_at,
            })

        return Response({
            'campaign_id': campaign.id,
            'campaign_title': campaign.title,
            'results': results,
        })

# Create Contribution
class CreateContributionView(APIView):
    """Create a contribution to a campaign"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, campaign_id):
        print("=" * 50)
        print("🔔 CONTRIBUTION REQUEST RECEIVED")
        print(f"Campaign ID: {campaign_id}")
        print(f"User: {request.user}")
        print(f"Request data: {request.data}")
        print(f"Request POST: {request.POST}")
        
        if not SiteSettings.payments_enabled():
            return Response({
                'error': 'Payments are disabled on this demo deployment. The M-Pesa/PayHero contribution flow is fully implemented in the code, but live transactions are turned off here.'
            }, status=status.HTTP_403_FORBIDDEN)

        campaign = get_object_or_404(Campaign, id=campaign_id)
        print(f"Campaign found: {campaign.title}")
        print(f"Campaign status: {campaign.status}")

        if campaign.status != 'active':
            print(f"❌ Campaign not active: {campaign.status}")
            return Response({
                'error': f'This campaign is not active. Status: {campaign.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        amount = request.data.get('amount')
        # Anonymous contributions are disabled in the current product flow.
        is_anonymous = False
        phone_number = request.data.get('phone_number')
        
        print(f"Amount: {amount} (type: {type(amount)})")
        print(f"Phone number: {phone_number}")
        print(f"Is anonymous: {is_anonymous}")
        
        # Validate amount
        if amount is None:
            print("❌ No amount provided")
            return Response({'error': 'Amount is required'}, status=400)
        
        try:
            amount = float(amount)
            print(f"Amount converted to float: {amount}")
        except (ValueError, TypeError) as e:
            print(f"❌ Invalid amount format: {amount}, error: {e}")
            return Response({'error': 'Invalid amount format'}, status=400)
        
        if amount <= 0:
            print(f"❌ Amount must be positive: {amount}")
            return Response({'error': 'Amount must be greater than 0'}, status=400)
        
        # Check minimum contribution (1 KSH global minimum)
        min_contrib = 1.0
        print(f"Minimum contribution: {min_contrib}")
        
        if amount < min_contrib:
            print(f"❌ Amount below minimum: {amount} < {min_contrib}")
            return Response({
                'error': f'Minimum contribution is Ksh {min_contrib}'
            }, status=400)
        
        # Validate phone number
        if not phone_number:
            print("❌ No phone number provided")
            return Response({'error': 'Phone number is required'}, status=400)
        
        phone_number = str(phone_number).strip()
        print(f"Phone number after cleaning: {phone_number}")
        
        # Check if phone number is valid Kenyan format
        import re
        phone_pattern = r'^(07|01)[0-9]{8}$'
        if not re.match(phone_pattern, phone_number):
            print(f"❌ Invalid phone format: {phone_number}")
            return Response({'error': 'Invalid phone number format. Use 07xxxxxxxx or 01xxxxxxxx'}, status=400)
        
        print("✅ All validations passed! Creating transaction...")
        
        # Generate unique external reference
        import uuid
        external_reference = f"KNOT-{campaign.id}-{uuid.uuid4().hex[:8].upper()}"
        
        # Create transaction with pending status
        transaction = Transaction.objects.create(
            transaction_type='contribution',
            payment_method='mpesa',
            amount=amount,
            phone_number=phone_number,
            user=request.user,
            campaign=campaign,
            payhero_reference=external_reference,
            description=f"Contribution to {campaign.title}",
            status='pending',  # Start as pending
            metadata={
                'is_anonymous': is_anonymous,
                'campaign_title': campaign.title,
                'campaign_slug': campaign.slug
            }
        )
        
        # ===== INITIATE PAYHERO PAYMENT =====
        from .payhero import payhero
        
        payment_result = payhero.initiate_payment(
            amount=amount,
            phone_number=phone_number,
            external_reference=external_reference,
            description=f"Contribution to {campaign.title}"
        )
        
        print(f"PayHero response: {payment_result}")
        
        # Check if payment was initiated successfully
        if 'error' in payment_result:
            transaction.status = 'failed'
            transaction.save()
            
            error_msg = payment_result.get('error', 'Payment initiation failed')
            details = payment_result.get('details', '')
            
            # Make error messages user-friendly
            if 'timeout' in error_msg.lower():
                error_msg = 'PayHero service is slow right now. Please try again in a moment.'
            elif 'connection' in error_msg.lower():
                error_msg = 'Network connection issue. Please check your internet and try again.'
            
            return Response({
                'error': error_msg,
                'details': details
            }, status=400)
        
        # Store the checkout request ID
        checkout_id = payment_result.get('CheckoutRequestID')
        if checkout_id:
            transaction.payhero_checkout_id = checkout_id
            transaction.save()
            print(f"✅ STK Push sent to {phone_number}")
        
        return Response({
            'message': 'STK Push sent to your phone. Please enter your PIN.',
            'checkout_request_id': checkout_id,
            'external_reference': external_reference,
            'transaction_id': transaction.transaction_id,
            'status': 'pending'
        }, status=200)
    

# Payment Callback
@csrf_exempt
def payhero_callback(request):
    """PayHero v2 Callback Handler"""
    print("=" * 50)
    print("🔔 PAYHERO CALLBACK RECEIVED")
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Parse the callback data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        print(f"Full callback data: {json.dumps(data, indent=2)}")
        
        # IMPORTANT: The data is nested under 'response' key
        if 'response' in data:
            response_data = data['response']
        else:
            response_data = data
        
        # Extract fields - now using the correct nested structure
        external_reference = response_data.get('ExternalReference')
        checkout_request_id = response_data.get('CheckoutRequestID')
        result_code = response_data.get('ResultCode')
        result_desc = response_data.get('ResultDesc')
        mpesa_receipt = response_data.get('MpesaReceiptNumber')
        amount = response_data.get('Amount')
        phone = response_data.get('Phone')
        
        print(f"✅ External Reference: {external_reference}")
        print(f"✅ Result Code: {result_code}")
        print(f"✅ Receipt: {mpesa_receipt}")
        
        if not external_reference:
            print("❌ No ExternalReference found")
            return JsonResponse({'error': 'No transaction reference'}, status=400)
        
        # Find the transaction
        from apps.payments.models import Transaction, Contribution
        
        transaction = Transaction.objects.filter(payhero_reference=external_reference).first()
        
        if not transaction:
            print(f"❌ Transaction not found for: {external_reference}")
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        print(f"✅ Found transaction: {transaction.transaction_id}")
        print(f"   Current status: {transaction.status}")
        
        # Handle based on result code
        if result_code == 0:
            # Payment successful!
            if transaction.status != 'completed':
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.mpesa_receipt = mpesa_receipt
                transaction.save()
                
                # Update campaign
                campaign = transaction.campaign
                campaign.funds_raised += transaction.amount
                campaign.contributor_count += 1
                campaign.save()
                
                # Create or get contribution record (idempotent)
                try:
                    Contribution.objects.get_or_create(
                        transaction=transaction,
                        defaults={
                            'user': transaction.user,
                            'campaign': campaign,
                            'amount': transaction.amount,
                            'is_anonymous': transaction.metadata.get('is_anonymous', False)
                        }
                    )
                except Exception as contrib_err:
                    print(f"⚠️ Warning creating contribution: {contrib_err}")
                
                print(f"✅✅✅ PAYMENT SUCCESSFUL!")
                print(f"   Campaign: {campaign.title}")
                print(f"   Amount: KES {transaction.amount}")
                print(f"   Receipt: {mpesa_receipt}")
                print(f"   New total: KES {campaign.funds_raised}")
                
                # Check if fully funded
                if campaign.funds_raised >= campaign.target_amount:
                    campaign.status = 'funded'
                    campaign.funded_date = timezone.now()
                    campaign.save()
                    print(f"🎉 CAMPAIGN FULLY FUNDED!")
                    
        elif result_code == 1032:
            # User cancelled
            transaction.status = 'cancelled'
            transaction.save()
            print(f"❌ User cancelled payment")
            
        elif result_code == 1037:
            # Timeout
            transaction.status = 'pending'
            transaction.save()
            print(f"⏰ Payment timeout")
            
        else:
            # Other error
            transaction.status = 'failed'
            transaction.save()
            print(f"❌ Payment failed: {result_desc}")
        
        return JsonResponse({'status': 'ok', 'result_code': result_code})
        
    except Exception as e:
        print(f"❌ Error processing callback: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

class VerifyPaymentView(APIView):
    """Manually verify a payment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        transaction_id = request.data.get('transaction_id')
        
        if not transaction_id:
            return Response({'error': 'Transaction ID required'}, status=400)
        
        try:
            transaction = Transaction.objects.get(
                transaction_id=transaction_id,
                user=request.user
            )
            
            if transaction.status == 'completed':
                return Response({
                    'status': 'completed',
                    'message': 'Payment already verified'
                })
            
            # Call PayHero to verify
            from .payhero import payhero
            verification = payhero.verify_payment(transaction.payhero_checkout_id)
            
            if verification.get('status') == 'completed':
                transaction.status = 'completed'
                transaction.completed_at = timezone.now()
                transaction.save()
                
                campaign = transaction.campaign
                campaign.funds_raised += transaction.amount
                campaign.contributor_count += 1
                campaign.save()
                
                Contribution.objects.get_or_create(
                    user=transaction.user,
                    campaign=campaign,
                    transaction=transaction,
                    defaults={
                        'amount': transaction.amount,
                        'is_anonymous': transaction.metadata.get('is_anonymous', False)
                    }
                )
                
                return Response({
                    'status': 'completed',
                    'message': 'Payment verified successfully'
                })
            
            return Response({
                'status': verification.get('status', 'pending'),
                'message': 'Payment still pending'
            })
            
        except Transaction.DoesNotExist:
            return Response({'error': 'Transaction not found'}, status=404)


class CheckPaymentStatusView(APIView):
    """Check payment status (for client polling)"""
    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _extract_status_payload(raw_payload):
        """Handle providers that nest response data under `response`."""
        if isinstance(raw_payload, dict) and isinstance(raw_payload.get('response'), dict):
            return raw_payload.get('response')
        return raw_payload if isinstance(raw_payload, dict) else {}

    @staticmethod
    def _normalize_status(value):
        return str(value or '').strip().lower()

    def _response_matches_transaction(self, payload, transaction):
        """Ensure upstream response corresponds to this transaction before acting on it."""
        known_refs = {
            str(ref).strip().lower()
            for ref in [
                transaction.payhero_reference,
                transaction.payhero_checkout_id,
                transaction.transaction_id,
            ]
            if ref
        }
        if not known_refs:
            return False

        response_refs = {
            str(ref).strip().lower()
            for ref in [
                payload.get('external_reference'),
                payload.get('ExternalReference'),
                payload.get('CheckoutRequestID'),
                payload.get('checkout_request_id'),
                payload.get('third_party_reference'),
                payload.get('payment_reference'),
            ]
            if ref
        }
        return bool(known_refs & response_refs)

    def _classify_upstream_status(self, payload):
        """Return one of: completed, failed, pending."""
        status_text = self._normalize_status(payload.get('status'))
        result_desc = self._normalize_status(payload.get('ResultDesc') or payload.get('result_description'))
        result_code = payload.get('ResultCode', payload.get('result_code'))
        normalized_code = str(result_code).strip() if result_code is not None else ''

        failed_markers = ('fail', 'cancel', 'declin', 'timeout', 'error', 'revers')
        success_markers = ('success', 'complete', 'paid')

        if normalized_code and normalized_code != '0':
            return 'failed'
        if any(marker in status_text for marker in failed_markers):
            return 'failed'
        if any(marker in result_desc for marker in failed_markers):
            return 'failed'

        if normalized_code == '0':
            return 'completed'
        if any(marker in status_text for marker in success_markers):
            return 'completed'
        if any(marker in result_desc for marker in success_markers):
            return 'completed'

        return 'pending'

    def _try_upstream_verification(self, transaction):
        refs_to_try = [
            transaction.payhero_checkout_id,
            transaction.payhero_reference,
            transaction.transaction_id,
        ]

        for ref in refs_to_try:
            if not ref:
                continue
            verification_raw = payhero.check_transaction_status(ref)
            verification = self._extract_status_payload(verification_raw)

            # Ignore provider responses that clearly belong to other transactions.
            if not self._response_matches_transaction(verification, transaction):
                continue

            state = self._classify_upstream_status(verification)
            if state in {'completed', 'failed'}:
                return state, verification

        # Fallback: reconcile from PayHero account ledger using external_reference.
        ledger_row = payhero.find_inbound_payment_by_external_reference(
            external_reference=transaction.payhero_reference,
            expected_amount=transaction.amount,
        )
        if ledger_row:
            receipt = ledger_row.get('provider_reference') or ledger_row.get('transaction_reference')
            return 'completed', {
                'status': 'COMPLETED',
                'MpesaReceiptNumber': receipt,
                'receipt': receipt,
                'external_reference': transaction.payhero_reference,
            }

        return 'pending', {}
    
    def get(self, request):
        external_reference = request.query_params.get('reference')
        
        if not external_reference:
            return Response({'error': 'Reference required'}, status=400)
        
        try:
            transaction = Transaction.objects.get(
                payhero_reference=external_reference,
                user=request.user
            )
            
            print(f"Checking transaction: {transaction.transaction_id}")
            print(f"Status: {transaction.status}")
            
            if transaction.status == 'completed':
                return Response({
                    'status': 'completed',
                    'transaction_id': transaction.transaction_id,
                    'amount': float(transaction.amount),
                    'receipt': transaction.mpesa_receipt
                })
            elif transaction.status == 'failed':
                return Response({
                    'status': 'failed',
                    'message': 'Payment failed'
                })
            elif transaction.status == 'cancelled':
                return Response({
                    'status': 'cancelled',
                    'message': 'Payment cancelled'
                })
            else:
                # Local record is pending; verify provider status with multiple references.
                upstream_state, verification = self._try_upstream_verification(transaction)

                if upstream_state == 'completed':
                    if transaction.status != 'completed':
                        transaction.status = 'completed'
                        transaction.completed_at = timezone.now()
                        transaction.mpesa_receipt = (
                            verification.get('MpesaReceiptNumber')
                            or verification.get('receipt')
                            or transaction.mpesa_receipt
                        )
                        transaction.save(update_fields=['status', 'completed_at', 'mpesa_receipt'])

                        campaign = transaction.campaign
                        if campaign is not None:
                            campaign.funds_raised += transaction.amount
                            campaign.contributor_count += 1
                            if campaign.funds_raised >= campaign.target_amount and campaign.status == 'active':
                                campaign.status = 'funded'
                                campaign.funded_date = timezone.now()
                                campaign.save(update_fields=['funds_raised', 'contributor_count', 'status', 'funded_date'])
                            else:
                                campaign.save(update_fields=['funds_raised', 'contributor_count'])

                        Contribution.objects.get_or_create(
                            user=transaction.user,
                            campaign=transaction.campaign,
                            transaction=transaction,
                            defaults={
                                'amount': transaction.amount,
                                'is_anonymous': transaction.metadata.get('is_anonymous', False)
                            }
                        )

                    return Response({
                        'status': 'completed',
                        'transaction_id': transaction.transaction_id,
                        'amount': float(transaction.amount),
                        'receipt': transaction.mpesa_receipt
                    })

                if upstream_state == 'failed':
                    if transaction.status != 'failed':
                        transaction.status = 'failed'
                        transaction.save(update_fields=['status'])
                    return Response({
                        'status': 'failed',
                        'message': 'Payment failed'
                    })

                return Response({
                    'status': 'pending',
                    'message': 'Waiting for payment confirmation'
                })
                
        except Transaction.DoesNotExist:
            return Response({'error': 'Transaction not found'}, status=404)
        except Exception as exc:
            print(f"❌ Error checking campaign payment status for {external_reference}: {exc}")
            return Response(
                {
                    'status': 'error',
                    'error': 'Unable to check payment status right now. Please retry shortly.'
                },
                status=500
            )
        


        

class CampaignDetailView(APIView):
    """Get a single campaign with fresh funds_raised and progress calculation"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, campaign_id):
        try:
            campaign = Campaign.objects.get(id=campaign_id)
            return Response({
                'id': campaign.id,
                'title': campaign.title,
                'slug': campaign.slug,
                'description': campaign.description,
                'target_amount': float(campaign.target_amount),
                'funds_raised': float(campaign.funds_raised),
                'progress_percentage': campaign.get_progress_percentage(),
                'days_remaining': campaign.days_remaining(),
                'status': campaign.status,
                'created_at': campaign.created_at,
                'contributor_count': campaign.contributor_count,
                'category_name': campaign.category.name if campaign.category else 'General',
            })
        except Campaign.DoesNotExist:
            return Response({'error': 'Campaign not found'}, status=404)
        except Exception as e:
            print(f"Error fetching campaign {campaign_id}: {e}")
            return Response({'error': 'Failed to fetch campaign'}, status=500)


class UserContributionsView(generics.ListAPIView):
    """Get current user's contributions"""
    serializer_class = ContributionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Contribution.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        completed = list(
            Contribution.objects.filter(user=request.user)
            .select_related('campaign', 'transaction')
            .order_by('-created_at')[:50]
        )

        completed_transaction_ids = {
            contrib.transaction_id
            for contrib in completed
            if contrib.transaction_id
        }

        pending_or_failed = list(
            Transaction.objects.filter(
                user=request.user,
                transaction_type='contribution',
            )
            .exclude(id__in=completed_transaction_ids)
            .select_related('campaign')
            .order_by('-created_at')[:20]
        )

        rows = []
        for contrib in completed:
            rows.append({
                'id': contrib.id,
                'user_name': getattr(contrib.user, 'username', ''),
                'campaign': contrib.campaign_id,
                'campaign_title': getattr(contrib.campaign, 'title', ''),
                'campaign_slug': getattr(contrib.campaign, 'slug', ''),
                'amount': float(contrib.amount),
                'is_anonymous': bool(contrib.is_anonymous),
                'created_at': contrib.created_at,
                'status': 'completed',
                'transaction_id': getattr(contrib.transaction, 'transaction_id', ''),
            })

        for txn in pending_or_failed:
            rows.append({
                'id': f"pending-{txn.id}",
                'user_name': getattr(txn.user, 'username', ''),
                'campaign': txn.campaign_id,
                'campaign_title': getattr(txn.campaign, 'title', 'Community Goal'),
                'campaign_slug': getattr(txn.campaign, 'slug', ''),
                'amount': float(txn.amount),
                'is_anonymous': bool(txn.metadata.get('is_anonymous', False)),
                'created_at': txn.created_at,
                'status': txn.status,
                'transaction_id': txn.transaction_id,
            })

        rows.sort(key=lambda item: item.get('created_at') or timezone.now(), reverse=True)
        return Response(rows)
#test view

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def test_callback(request):
    """Test endpoint to verify PayHero can reach your server"""
    print("=" * 50)
    print("TEST CALLBACK RECEIVED")
    print(f"Method: {request.method}")
    print(f"Headers: {dict(request.headers)}")
    
    try:
        if request.method == 'POST':
            data = json.loads(request.body) if request.body else {}
            print(f"Data: {data}")
        else:
            print("GET request received - callback working!")
            
    except Exception as e:
        print(f"Error: {e}")
    
    return JsonResponse({'status': 'ok', 'message': 'Callback endpoint working'})

