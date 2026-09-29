import requests
import base64
import logging
from django.conf import settings
from decimal import Decimal, InvalidOperation
from time import sleep

logger = logging.getLogger(__name__)

class PayHeroAPI:
    """PayHero v2 API Integration"""
    
    def __init__(self):
        self.username = getattr(settings, 'PAYHERO_USERNAME', '')
        self.api_key = getattr(settings, 'PAYHERO_API_KEY', '')
        self.channel_id = getattr(settings, 'PAYHERO_CHANNEL_ID', '')
        self.base_url = getattr(settings, 'PAYHERO_BASE_URL', 'https://backend.payhero.co.ke')
        self.callback_url = getattr(settings, 'PAYHERO_CALLBACK_URL', '')
        
    def _get_auth_header(self):
        """Create Basic Auth header"""
        auth_string = f"{self.username}:{self.api_key}"
        auth_bytes = auth_string.encode('utf-8')
        auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')
        return f"Basic {auth_base64}"
    
    def format_phone(self, phone):
        """Format phone number for PayHero (expects 07xxxxxxxx)"""
        phone = ''.join(filter(str.isdigit, phone))
        if phone.startswith('254'):
            phone = '0' + phone[3:]
        elif phone.startswith('+254'):
            phone = '0' + phone[4:]
        if not phone.startswith('0'):
            phone = '0' + phone
        return phone
    
    def initiate_payment(self, amount, phone_number, external_reference, description, callback_url=None):
        """Initiate STK Push payment with retry logic"""
        headers = {
            'Authorization': self._get_auth_header(),
            'Content-Type': 'application/json'
        }
        
        formatted_phone = self.format_phone(phone_number)
        
        payload = {
            'amount': int(round(float(amount))),
            'phone_number': formatted_phone,
            'channel_id': self.channel_id,
            'provider': 'm-pesa',
            'external_reference': external_reference,
            'callback_url': callback_url or self.callback_url,
            'description': description[:100]
        }
        
        logger.info(f"📤 Initiating PayHero payment with payload: {payload}")
        print(f"Sending payload to PayHero: {payload}")
        
        # Retry logic for transient failures
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/v2/payments",
                    headers=headers,
                    json=payload,
                    timeout=60  # Increased from 30 to 60 seconds
                )
                
                logger.info(f"PayHero initiate response status: {response.status_code}")
                logger.info(f"PayHero initiate response body: {response.text}")
                print(f"PayHero response status: {response.status_code}")
                print(f"PayHero response body: {response.text}")
                
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    # Extract all possible transaction IDs PayHero might return
                    logger.info(f"✅ PayHero payment initiated successfully")
                    logger.info(f"   Response keys: {list(response_data.keys())}")
                    logger.info(f"   Full response: {response_data}")
                    return response_data
                else:
                    logger.warning(f"❌ PayHero API error {response.status_code}: {response.text}")
                    return {
                        'error': f"API error: {response.status_code}",
                        'details': response.text
                    }
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⏱️  PayHero timeout (attempt {attempt + 1}/{max_retries})")
                print(f"PayHero timeout (attempt {attempt + 1}/{max_retries})")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    sleep(retry_delay)
                else:
                    logger.error("PayHero timeout after all retries")
                    return {
                        'error': 'Payment service timeout. Please try again in a moment.',
                        'details': 'PayHero API is taking longer than expected'
                    }
                    
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {e}", exc_info=True)
                return {
                    'error': 'Network connection error. Please check your internet and try again.',
                    'details': str(e)
                }
                
            except Exception as e:
                logger.error(f"Error calling PayHero: {e}", exc_info=True)
                print(f"Error calling PayHero: {e}")
                return {'error': str(e)}
        
        # Shouldn't reach here, but just in case
        return {
            'error': 'Payment initiation failed after multiple attempts'
        }
    
    def check_transaction_status(self, external_reference):
        """Check transaction status from PayHero"""
        headers = {
            'Authorization': self._get_auth_header(),
            'Content-Type': 'application/json'
        }
        
        if not external_reference:
            logger.warning("❌ No reference provided for status check")
            return {'status': 'pending', 'error': 'No reference provided'}
        
        logger.info(f"🔍 Checking PayHero transaction status for reference: {external_reference}")
        
        try:
            # PayHero status endpoint is reliable with `reference` lookups only.
            response = requests.get(
                f"{self.base_url}/api/v2/transaction-status",
                headers=headers,
                params={'reference': external_reference},
                timeout=30
            )

            logger.info(f"   Response [reference]: status={response.status_code}, body={response.text[:200]}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ PayHero returned status data: {data}")
                return data

            if response.status_code == 404:
                return {
                    'status': 'not_found',
                    'error': 'Transaction not found in status endpoint',
                    'code': 404,
                }

            logger.warning(f"⚠️ PayHero returned {response.status_code}")
            logger.warning(f"   Response: {response.text}")
            return {
                'status': 'pending',
                'error': f"Status check failed ({response.status_code})",
                'code': response.status_code
            }
                
        except Exception as e:
            logger.error(f"❌ PayHero status check error: {e}", exc_info=True)
            return {'status': 'pending', 'error': str(e)}

    def find_inbound_payment_by_external_reference(self, external_reference, expected_amount=None):
        """Find matching inbound payment in PayHero transactions ledger."""
        headers = {
            'Authorization': self._get_auth_header(),
            'Content-Type': 'application/json'
        }

        try:
            response = requests.get(
                f"{self.base_url}/api/v2/transactions",
                headers=headers,
                params={'external_reference': external_reference},
                timeout=30
            )

            if response.status_code != 200:
                logger.warning(
                    "⚠️ PayHero transactions lookup failed (%s): %s",
                    response.status_code,
                    response.text[:300],
                )
                return None

            payload = response.json() if response.text else {}
            transactions = payload.get('transactions', []) if isinstance(payload, dict) else []
            if not isinstance(transactions, list):
                return None

            expected = None
            if expected_amount is not None:
                try:
                    expected = Decimal(str(expected_amount))
                except (InvalidOperation, TypeError, ValueError):
                    expected = None

            for row in transactions:
                if not isinstance(row, dict):
                    continue
                if str(row.get('external_reference') or '').strip() != str(external_reference).strip():
                    continue
                if str(row.get('transaction_type') or '').strip().lower() != 'inbound_payment':
                    continue

                if expected is not None:
                    try:
                        ledger_amount = Decimal(str(row.get('amount', 0)))
                    except (InvalidOperation, TypeError, ValueError):
                        continue
                    if ledger_amount < expected:
                        continue

                return row

            return None
        except Exception as e:
            logger.error(f"❌ PayHero transactions lookup error: {e}", exc_info=True)
            return None

payhero = PayHeroAPI()