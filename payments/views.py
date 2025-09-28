# payments/views.py - Updated with real STK Push

import requests
import base64
import json
import logging
from datetime import datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from .models import SubscriptionPayment

logger = logging.getLogger(__name__)


class MpesaSTKPush:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.api_url = "https://sandbox.safaricom.co.ke" if settings.MPESA_ENVIRONMENT == 'sandbox' else "https://api.safaricom.co.ke"
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY

    def get_access_token(self):
        """Get OAuth access token from Safaricom"""
        try:
            url = f"{self.api_url}/oauth/v1/generate?grant_type=client_credentials"
            credentials = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()

            headers = {
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json'
            }

            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()['access_token']
            else:
                logger.error(f"Failed to get access token: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None

    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc):
        """Initiate STK Push to user's phone"""
        access_token = self.get_access_token()
        if not access_token:
            return {'success': False, 'message': 'Failed to get access token'}

        try:
            url = f"{self.api_url}/mpesa/stkpush/v1/processrequest"
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode()).decode()

            payload = {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            logger.info(f"Initiating STK Push for {phone_number}, Amount: {amount}")
            response = requests.post(url, json=payload, headers=headers)
            result = response.json()

            logger.info(f"STK Push response: {result}")

            if response.status_code == 200 and result.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'checkout_request_id': result.get('CheckoutRequestID'),
                    'merchant_request_id': result.get('MerchantRequestID'),
                    'message': 'STK Push sent successfully'
                }
            else:
                return {
                    'success': False,
                    'message': result.get('errorMessage', result.get('CustomerMessage', 'STK Push failed'))
                }

        except Exception as e:
            logger.error(f"STK Push error: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}


@login_required
def subscribe(request):
    if request.user.subscription_paid:
        messages.info(request, 'You already have an active subscription.')
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')

        if not phone_number:
            messages.error(request, 'Please provide your M-Pesa phone number.')
            return render(request, 'payments/subscribe.html', {
                'subscription_price': settings.SUBSCRIPTION_PRICE
            })

        # Format phone number (ensure it starts with 254)
        if phone_number.startswith('0'):
            formatted_phone = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            formatted_phone = phone_number[1:]
        elif not phone_number.startswith('254'):
            formatted_phone = '254' + phone_number
        else:
            formatted_phone = phone_number

        try:
            # Create unique account reference
            account_reference = f"SUB_{request.user.username}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Initiate STK Push first
            mpesa = MpesaSTKPush()
            result = mpesa.initiate_stk_push(
                phone_number=formatted_phone,
                amount=settings.SUBSCRIPTION_PRICE,
                account_reference=account_reference,
                transaction_desc=f"BazuuConnect Subscription - {request.user.username}"
            )

            if result['success']:
                # Create payment record with STK Push details
                payment = SubscriptionPayment.objects.create(
                    user=request.user,
                    amount=settings.SUBSCRIPTION_PRICE,
                    phone_number=formatted_phone,
                    checkout_request_id=result['checkout_request_id'],
                    merchant_request_id=result['merchant_request_id'],
                    account_reference=account_reference,
                    status='pending'
                )

                messages.success(request,
                                 f'Payment request sent to {formatted_phone}. Please check your phone for M-Pesa prompt.')
                return render(request, 'payments/payment_pending.html', {
                    'payment': payment,
                    'phone_number': formatted_phone,
                    'amount': settings.SUBSCRIPTION_PRICE,
                    'checkout_request_id': result['checkout_request_id']
                })
            else:
                messages.error(request, f'Payment request failed: {result["message"]}')
                return render(request, 'payments/subscribe.html', {
                    'subscription_price': settings.SUBSCRIPTION_PRICE
                })

        except Exception as e:
            logger.error(f"Payment creation error: {str(e)}")
            messages.error(request, 'Payment request failed. Please try again.')

    context = {
        'subscription_price': settings.SUBSCRIPTION_PRICE,
    }
    return render(request, 'payments/subscribe.html', context)


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa callback/webhook"""
    if request.method == 'POST':
        try:
            callback_data = json.loads(request.body)
            logger.info(f"M-Pesa Callback received: {callback_data}")

            # Extract STK callback data (correct M-Pesa format)
            stk_callback = callback_data.get('Body', {}).get('stkCallback', {})

            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')

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
                            if item.get('Name') == 'MpesaReceiptNumber':
                                receipt_number = item.get('Value')
                            elif item.get('Name') == 'TransactionDate':
                                # Convert transaction date from format: 20241001143022
                                transaction_date = datetime.strptime(str(item.get('Value')), '%Y%m%d%H%M%S')
                            elif item.get('Name') == 'Amount':
                                amount = item.get('Value')

                        # Update payment record
                        payment.status = 'completed'
                        payment.mpesa_receipt_number = receipt_number
                        payment.transaction_date = transaction_date
                        payment.save()

                        # Update user subscription status
                        user = payment.user
                        user.subscription_paid = True
                        user.save()

                        logger.info(
                            f"Payment completed successfully for user {user.username}, Receipt: {receipt_number}")

                    else:  # Failed or cancelled
                        payment.status = 'failed'
                        payment.failure_reason = result_desc
                        payment.save()

                        logger.warning(
                            f"Payment failed for CheckoutRequestID: {checkout_request_id}, Reason: {result_desc}")

                except SubscriptionPayment.DoesNotExist:
                    logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")

        except Exception as e:
            logger.error(f"Callback processing error: {str(e)}")

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@login_required
def check_payment_status(request):
    """AJAX endpoint to check payment status"""
    payment_id = request.GET.get('payment_id')

    try:
        payment = SubscriptionPayment.objects.get(id=payment_id, user=request.user)
        return JsonResponse({
            'status': payment.status,
            'receipt_number': payment.mpesa_receipt_number,
            'user_subscribed': request.user.subscription_paid
        })
    except SubscriptionPayment.DoesNotExist:
        return JsonResponse({'status': 'not_found'})


@login_required
def payment_success(request):
    return render(request, 'payments/success.html')


@login_required
def payment_cancel(request):
    return render(request, 'payments/cancel.html')


# Enhanced simulation for sandbox testing
@login_required
def simulate_payment_success(request, payment_id):
    """Simulate successful payment for sandbox testing"""
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