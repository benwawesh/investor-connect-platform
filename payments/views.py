# payments/views.py - Complete version with consolidated callback

import requests
import base64
import json
import logging
import uuid
from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction as db_transaction
from .models import SubscriptionPayment
from accounts.models import CustomUser

logger = logging.getLogger(__name__)


class MpesaSTKPush:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.api_url = settings.MPESA_API_URL
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.environment = settings.MPESA_ENVIRONMENT

    def get_access_token(self):
        """Get OAuth access token from Safaricom"""
        try:
            url = f"{self.api_url}/oauth/v1/generate?grant_type=client_credentials"
            credentials = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()

            headers = {
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json'
            }

            logger.info(f"Getting access token from {self.environment} environment")
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                logger.info(f"Access token obtained successfully - Environment: {self.environment}")
                return response.json()['access_token']
            else:
                logger.error(f"Failed to get access token: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None

    def format_phone_number(self, phone):
        """Format phone number to 254XXXXXXXXX"""
        phone = str(phone).strip()

        # Remove any spaces, dashes, or plus signs
        phone = phone.replace(' ', '').replace('-', '').replace('+', '')

        # If starts with 0, replace with 254
        if phone.startswith('0'):
            phone = '254' + phone[1:]

        # If starts with 254, use as is
        elif phone.startswith('254'):
            phone = phone

        # If just 9 digits, add 254
        elif len(phone) == 9:
            phone = '254' + phone

        return phone

    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push to user's phone"""
        access_token = self.get_access_token()
        if not access_token:
            return {'success': False, 'message': 'Failed to get access token'}

        try:
            # Format phone number
            formatted_phone = self.format_phone_number(phone_number)

            url = f"{self.api_url}/mpesa/stkpush/v1/processrequest"
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode()).decode()

            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": formatted_phone,
                "PartyB": self.shortcode,
                "PhoneNumber": formatted_phone,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            logger.info(
                f"Initiating STK Push - Environment: {self.environment}, Phone: {formatted_phone}, Amount: {amount}, Shortcode: {self.shortcode}")
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            result = response.json()

            logger.info(f"STK Push response: {result}")

            if response.status_code == 200 and result.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'checkout_request_id': result.get('CheckoutRequestID'),
                    'merchant_request_id': result.get('MerchantRequestID'),
                    'message': 'STK Push sent successfully',
                    'formatted_phone': formatted_phone
                }
            else:
                error_message = result.get('errorMessage', result.get('CustomerMessage', 'STK Push failed'))
                logger.error(f"STK Push failed: {error_message}")
                return {
                    'success': False,
                    'message': error_message
                }

        except Exception as e:
            logger.error(f"STK Push error: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}


@login_required
def subscribe(request):
    """Handle subscription payments for existing users"""
    if request.user.subscription_paid:
        messages.info(request, 'You already have an active subscription.')
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')

        if not phone_number:
            messages.error(request, 'Please provide your M-Pesa phone number.')
            return render(request, 'payments/subscribe.html', {
                'subscription_price': settings.SUBSCRIPTION_PRICE,
                'environment': settings.MPESA_ENVIRONMENT
            })

        try:
            # Create unique account reference
            account_reference = f"SUB_{request.user.username}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Initiate STK Push
            mpesa = MpesaSTKPush()
            result = mpesa.initiate_stk_push(
                phone_number=phone_number,
                amount=settings.SUBSCRIPTION_PRICE,
                account_reference=account_reference,
                transaction_desc=f"BazuuConnect Subscription - {request.user.username}"
            )

            if result['success']:
                # Create payment record with STK Push details
                payment = SubscriptionPayment.objects.create(
                    user=request.user,
                    transaction_type='SUBSCRIPTION',
                    amount=settings.SUBSCRIPTION_PRICE,
                    phone_number=result['formatted_phone'],
                    checkout_request_id=result['checkout_request_id'],
                    merchant_request_id=result['merchant_request_id'],
                    account_reference=account_reference,
                    status='pending'
                )

                messages.success(request,
                                 f'Payment request sent to {result["formatted_phone"]}. Please check your phone for M-Pesa prompt.')
                return render(request, 'payments/payment_pending.html', {
                    'payment': payment,
                    'phone_number': result['formatted_phone'],
                    'amount': settings.SUBSCRIPTION_PRICE,
                    'checkout_request_id': result['checkout_request_id'],
                    'environment': settings.MPESA_ENVIRONMENT
                })
            else:
                messages.error(request, f'Payment request failed: {result["message"]}')
                return render(request, 'payments/subscribe.html', {
                    'subscription_price': settings.SUBSCRIPTION_PRICE,
                    'environment': settings.MPESA_ENVIRONMENT
                })

        except Exception as e:
            logger.error(f"Payment creation error: {str(e)}")
            messages.error(request, 'Payment request failed. Please try again.')

    context = {
        'subscription_price': settings.SUBSCRIPTION_PRICE,
        'environment': settings.MPESA_ENVIRONMENT,
        'shortcode': settings.MPESA_SHORTCODE
    }
    return render(request, 'payments/subscribe.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """
    CONSOLIDATED M-Pesa callback handler for BOTH REGISTRATION and SUBSCRIPTION payments
    This replaces the duplicate callback in accounts/views.py
    """
    try:
        # Log the raw callback data
        callback_body = request.body.decode('utf-8')
        logger.info(f"M-Pesa Callback received ({settings.MPESA_ENVIRONMENT}): {callback_body}")

        callback_data = json.loads(callback_body)

        # Extract STK callback data (correct M-Pesa format)
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})

        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc', '')

        logger.info(f"Processing callback for CheckoutRequestID: {checkout_request_id}, ResultCode: {result_code}")

        if checkout_request_id:
            try:
                payment = SubscriptionPayment.objects.get(
                    checkout_request_id=checkout_request_id
                )

                if result_code == 0:  # Success
                    # Extract payment details from callback metadata
                    callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                    receipt_number = None
                    transaction_date = None
                    amount = None

                    for item in callback_metadata:
                        name = item.get('Name')
                        value = item.get('Value')

                        if name == 'MpesaReceiptNumber':
                            receipt_number = value
                        elif name == 'TransactionDate':
                            # Convert transaction date from format: 20241001143022
                            try:
                                transaction_date = datetime.strptime(str(value), '%Y%m%d%H%M%S')
                            except:
                                transaction_date = timezone.now()
                        elif name == 'Amount':
                            amount = value

                    # Update payment record
                    payment.status = 'completed'
                    payment.mpesa_receipt_number = receipt_number
                    payment.transaction_date = transaction_date
                    payment.save()

                    logger.info(f"Payment {payment.id} completed with receipt: {receipt_number}")

                    # Handle based on transaction type
                    if payment.transaction_type == 'REGISTRATION':
                        # Create new user account for registration payments
                        logger.info(f"Creating user account for registration payment: {payment.id}")
                        create_user_from_payment_transaction(payment)

                    elif payment.transaction_type == 'SUBSCRIPTION':
                        # Update existing user subscription
                        if payment.user:
                            payment.user.subscription_paid = True
                            payment.user.save()
                            logger.info(
                                f"Subscription updated for user {payment.user.username}, Receipt: {receipt_number}")
                        else:
                            logger.warning(f"Subscription payment {payment.id} has no associated user")

                    logger.info(
                        f"Payment completed successfully - Type: {payment.transaction_type}, Receipt: {receipt_number}, Environment: {settings.MPESA_ENVIRONMENT}")

                else:  # Failed or cancelled
                    payment.status = 'failed'
                    payment.failure_reason = result_desc
                    payment.save()

                    logger.warning(
                        f"Payment {payment.id} failed for CheckoutRequestID: {checkout_request_id}, Reason: {result_desc}")

            except SubscriptionPayment.DoesNotExist:
                logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in callback: {e}")
    except Exception as e:
        logger.error(f"Callback processing error: {e}")

    # Always return success to M-Pesa to acknowledge receipt
    return JsonResponse({
        'ResultCode': 0,
        'ResultDesc': 'Accepted'
    })


def create_user_from_payment_transaction(payment_transaction):
    """Create user account after successful registration payment"""
    try:
        with db_transaction.atomic():
            # Check if user already exists
            if CustomUser.objects.filter(username=payment_transaction.temp_username).exists():
                logger.warning(f"User {payment_transaction.temp_username} already exists")
                return

            # Additional checks
            if CustomUser.objects.filter(email=payment_transaction.temp_email).exists():
                logger.warning(f"Email {payment_transaction.temp_email} already exists")
                return

            # if CustomUser.objects.filter(phone_number=payment_transaction.phone_number).exists():
            #     logger.warning(f"Phone number {payment_transaction.phone_number} already exists")
            #     return

            # Create the user account
            user = CustomUser.objects.create(
                username=payment_transaction.temp_username,
                email=payment_transaction.temp_email,
                password=make_password(payment_transaction.temp_password),
                phone_number=payment_transaction.phone_number,
                user_type=payment_transaction.temp_user_type if hasattr(payment_transaction,
                                                                        'temp_user_type') else 'regular',
                subscription_paid=True,
                is_verified=True,
            )

            # Link payment to user
            payment_transaction.user = user
            payment_transaction.save()

            logger.info(f"User account created successfully: {user.username} (ID: {user.id})")

            # TODO: Send welcome email with credentials

    except Exception as e:
        logger.error(f"Error creating user from payment: {str(e)}")


@login_required
def check_payment_status(request):
    """AJAX endpoint to check payment status"""
    payment_id = request.GET.get('payment_id')

    try:
        payment = SubscriptionPayment.objects.get(id=payment_id, user=request.user)
        return JsonResponse({
            'status': payment.status,
            'receipt_number': payment.mpesa_receipt_number,
            'user_subscribed': request.user.subscription_paid,
            'environment': settings.MPESA_ENVIRONMENT
        })
    except SubscriptionPayment.DoesNotExist:
        return JsonResponse({'status': 'not_found'})


@login_required
def payment_success(request):
    return render(request, 'payments/success.html', {
        'environment': settings.MPESA_ENVIRONMENT
    })


@login_required
def payment_cancel(request):
    return render(request, 'payments/cancel.html')


@login_required
def simulate_payment_success(request, payment_id):
    """Simulate successful payment for sandbox testing ONLY"""
    if settings.MPESA_ENVIRONMENT == 'sandbox' and settings.DEBUG:
        try:
            payment = SubscriptionPayment.objects.get(id=payment_id, user=request.user)

            # Simulate successful payment
            payment.status = 'completed'
            payment.mpesa_receipt_number = f'SANDBOX{timezone.now().strftime("%Y%m%d%H%M%S")}'
            payment.transaction_date = timezone.now()
            payment.save()

            # Update user subscription
            request.user.subscription_paid = True
            request.user.save()

            messages.success(request, 'Payment simulation completed successfully!')
            return redirect('payments:payment_success')

        except SubscriptionPayment.DoesNotExist:
            messages.error(request, 'Payment not found.')
    else:
        messages.error(request, 'Payment simulation only available in sandbox mode.')

    return redirect('accounts:dashboard')