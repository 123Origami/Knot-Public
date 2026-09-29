import requests
import hashlib
import hmac
import json
from django.conf import settings
from django.utils import timezone

class PayheroClient:
    """
    Client for Payhero API integration.
    Handles M-Pesa STK Push, card payments, and payouts.
    """
    
    BASE_URL = "https://api.payhero.co.ke/api/v1"
    SANDBOX_URL = "https://sandbox.payhero.co.ke/api/v1"
    
    def __init__(self, sandbox=True):
        self.api_key = settings.PAYHERO_API_KEY
        self.api_secret = settings.PAYHERO_API_SECRET
        self.base_url = self.SANDBOX_URL if sandbox else self.BASE_URL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def stk_push(self, phone_number, amount, reference, description):
        """
        Initiate M-Pesa STK Push
        
        Args:
            phone_number (str): Customer phone number (e.g., 0712345678)
            amount (int): Amount in KES
            reference (str): Transaction reference
            description (str): Transaction description
        
        Returns:
            dict: Payhero API response
        """
        # Format phone number (remove 0, add 254)
        if phone_number.startswith('0'):
            phone = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone = phone_number[1:]
        else:
            phone = phone_number
        
        payload = {
            'amount': int(amount),
            'phone': phone,
            'reference': reference,
            'description': description
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def charge_card(self, card_token, amount, reference, description):
        """
        Process card payment
        
        Args:
            card_token (str): Tokenized card from Payhero.js
            amount (int): Amount in KES
            reference (str): Transaction reference
            description (str): Transaction description
        
        Returns:
            dict: Payhero API response
        """
        payload = {
            'amount': int(amount),
            'card_token': card_token,
            'reference': reference,
            'description': description
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/card/charge",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def check_transaction_status(self, reference):
        """
        Check transaction status
        
        Args:
            reference (str): Transaction reference
        
        Returns:
            dict: Transaction status
        """
        try:
            response = requests.get(
                f"{self.base_url}/transaction/status/{reference}",
                headers=self.headers,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def initiate_payout(self, bank_details, amount, reference):
        """
        Initiate bank transfer payout
        
        Args:
            bank_details (dict): Bank details (bank_code, account_number, account_name)
            amount (int): Amount in KES
            reference (str): Payout reference
        
        Returns:
            dict: Payhero API response
        """
        payload = {
            'amount': int(amount),
            'reference': reference,
            'bank_code': bank_details['bank_code'],
            'account_number': bank_details['account_number'],
            'account_name': bank_details['account_name'],
            'narration': 'Campaign payout from Knot'
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/payout/bank",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def verify_webhook_signature(payload, signature):
        """
        Verify webhook signature from Payhero
        
        Args:
            payload (bytes): Raw request body
            signature (str): Signature from Payhero header
        
        Returns:
            bool: True if signature is valid
        """
        expected = hmac.new(
            key=settings.PAYHERO_WEBHOOK_SECRET.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)