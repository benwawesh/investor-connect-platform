from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
import json
import logging
from .models import SubscriptionPayment

logger = logging.getLogger(__name__)


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
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number

        try:
            # Create payment record
            payment = SubscriptionPayment.objects.create(
                user=request.user,
                amount=settings.SUBSCRIPTION_PRICE,
                phone_number=phone_number,
                status='pending'
            )

            messages.success(request,
                             f'Payment request sent to {phone_number}. Please check your phone for M-Pesa prompt.')
            return render(request, 'payments/payment_pending.html', {
                'payment': payment,
                'phone_number': phone_number
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

            # Extract relevant data from callback
            checkout_request_id = callback_data.get('CheckoutRequestID')
            result_code = callback_data.get('ResultCode')

            if result_code == 0:  # Success
                try:
                    payment = SubscriptionPayment.objects.get(
                        checkout_request_id=checkout_request_id
                    )
                    payment.status = 'completed'
                    payment.mpesa_receipt_number = callback_data.get('MpesaReceiptNumber', '')
                    payment.save()

                    # Update user subscription status
                    user = payment.user
                    user.subscription_paid = True
                    user.save()

                    logger.info(f"Payment completed for user {user.username}")

                except SubscriptionPayment.DoesNotExist:
                    logger.error(f"Payment not found: {checkout_request_id}")

        except Exception as e:
            logger.error(f"Callback processing error: {str(e)}")

    return JsonResponse({'status': 'success'})


@login_required
def payment_success(request):
    return render(request, 'payments/success.html')


@login_required
def payment_cancel(request):
    return render(request, 'payments/cancel.html')


# Temporary view to manually complete payment (for testing)
@login_required
def simulate_payment_success(request, payment_id):
    """Temporary view to simulate successful payment - REMOVE IN PRODUCTION"""
    if settings.DEBUG:  # Only in development
        try:
            payment = SubscriptionPayment.objects.get(id=payment_id, user=request.user)
            payment.status = 'completed'
            payment.mpesa_receipt_number = f'TEST{timezone.now().strftime("%Y%m%d%H%M%S")}'
            payment.save()

            # Update user subscription
            request.user.subscription_paid = True
            request.user.save()

            messages.success(request, 'Payment completed successfully!')
            return redirect('payments:payment_success')

        except SubscriptionPayment.DoesNotExist:
            messages.error(request, 'Payment not found.')

    return redirect('accounts:dashboard')