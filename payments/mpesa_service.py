# payments/mpesa_service.py
import requests
import base64
import datetime
import json
from django.conf import settings
from decouple import config
import logging

logger = logging.getLogger(__name__)


class MpesaService:
    def __init__(self):
        # Get environment
        self.environment = config('MPESA_ENVIRONMENT', default='sandbox')
        
        # Load credentials based on environment
        if self.environment == 'production':
            self.consumer_key = config('MPESA_PROD_CONSUMER_KEY')
            self.consumer_secret = config('MPESA_PROD_CONSUMER_SECRET')
            self.shortcode = config('MPESA_PROD_SHORTCODE')
            self.till_number = config('MPESA_PROD_TILL_NUMBER')
            self.passkey = config('MPESA_PROD_PASSKEY')
            self.base_url = "https://api.safaricom.co.ke"
        else:
            self.consumer_key = config('MPESA_SANDBOX_CONSUMER_KEY')
            self.consumer_secret = config('MPESA_SANDBOX_CONSUMER_SECRET')
            self.shortcode = config('MPESA_SANDBOX_SHORTCODE')
            self.till_number = config('MPESA_SANDBOX_SHORTCODE')
            self.passkey = config('MPESA_SANDBOX_PASSKEY')
            self.base_url = "https://sandbox.safaricom.co.ke"
        
        self.callback_url = config('MPESA_CALLBACK_URL')
        self.token_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        self.stk_query_url = f"{self.base_url}/mpesa/stkpushquery/v1/query"

        logger.info(f"M-Pesa Service initialized for {self.environment} environment")

    def get_access_token(self):
        """Get OAuth access token from Safaricom"""
        try:
            # Create basic auth string
            auth_string = f"{self.consumer_key}:{self.consumer_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')

            headers = {
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            }

            logger.info(f"Requesting access token from: {self.token_url}")

            response = requests.get(self.token_url, headers=headers, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get('access_token')

            if access_token:
                logger.info("Access token obtained successfully")
                return access_token
            else:
                logger.error(f"No access token in response: {token_data}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting access token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting access token: {e}")
            return None

    def generate_password(self):
        """Generate password for STK push"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        password_string = f"{self.shortcode}{self.passkey}{timestamp}"
        password_bytes = password_string.encode('ascii')
        password_b64 = base64.b64encode(password_bytes).decode('ascii')
        return password_b64, timestamp

    def format_phone_number(self, phone):
        """Format phone number to 254XXXXXXXXX"""
        phone = str(phone).strip()

        # Remove any non-digit characters except +
        import re
        phone = re.sub(r'[^\d+]', '', phone)

        if phone.startswith('0'):
            return '254' + phone[1:]
        elif phone.startswith('+254'):
            return phone[1:]
        elif phone.startswith('254'):
            return phone
        elif len(phone) == 9:
            return '254' + phone
        else:
            return '254' + phone

    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK push payment"""
        try:
            # Get access token
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'message': 'Failed to get access token'}

            # Format phone number
            formatted_phone = self.format_phone_number(phone_number)
            logger.info(f"Formatted phone number: {formatted_phone}")

            # DEBUG LOGGING
            logger.info("=== STK PUSH DEBUG ===")
            logger.info(f"Environment: {self.environment}")
            logger.info(f"BusinessShortCode: {self.shortcode}")
            till_value = getattr(self, 'till_number', 'NOT SET')
            logger.info(f"PartyB (Till): {till_value}")
            logger.info(f"Base URL: {self.base_url}")
            logger.info("======================")

            # Generate password and timestamp
            password, timestamp = self.generate_password()

            # Request headers
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            # Request payload
            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerBuyGoodsOnline",
                "Amount": int(amount),
                "PartyA": formatted_phone,
                "PartyB": self.till_number if hasattr(self, 'till_number') else self.shortcode,
                "PhoneNumber": formatted_phone,
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }

            logger.info(f"STK Push payload: {json.dumps(payload, indent=2)}")

            # Make STK push request
            response = requests.post(self.stk_push_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_data = response.json()
            logger.info(f"STK Push response: {json.dumps(response_data, indent=2)}")

            if response_data.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'message': 'STK push sent successfully',
                    'checkout_request_id': response_data.get('CheckoutRequestID'),
                    'merchant_request_id': response_data.get('MerchantRequestID'),
                    'response_data': response_data
                }
            else:
                error_message = response_data.get('errorMessage') or response_data.get('ResponseDescription', 'STK push failed')
                return {
                    'success': False,
                    'message': error_message,
                    'response_data': response_data
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during STK push: {e}")
            return {
                'success': False,
                'message': f'Network error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error during STK push: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    def query_stk_push(self, checkout_request_id):
        """Query the status of an STK push transaction"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {'success': False, 'message': 'Failed to get access token'}

            password, timestamp = self.generate_password()

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }

            response = requests.post(self.stk_query_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            response_data = response.json()
            logger.info(f"STK Query response: {json.dumps(response_data, indent=2)}")

            return {
                'success': True,
                'response_data': response_data
            }

        except Exception as e:
            logger.error(f"Error querying STK push: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    def test_connection(self):
        """Test the M-Pesa API connection"""
        try:
            access_token = self.get_access_token()
            if access_token:
                return {
                    'success': True,
                    'message': 'M-Pesa API connection successful',
                    'environment': self.environment,
                    'token_length': len(access_token) if access_token else 0
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to connect to M-Pesa API'
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }
