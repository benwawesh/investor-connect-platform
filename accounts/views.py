# accounts/views.py - COMPLETE UPDATED VERSION

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import uuid
import logging
from payments.mpesa_service import MpesaService
from django.views.decorators.http import require_http_methods
from .forms import SignUpWithPaymentForm
from .models import CustomUser, UserProfileExtension, NotificationSettings
from payments.models import SubscriptionPayment,PlatformSettings
from django.conf import settings
from pitches.models import IdeaPitch
from django.shortcuts import render, redirect, get_object_or_404

# Profile management form imports
from .forms import (
    CustomUserProfileForm, UserProfileExtensionForm,
    CustomPasswordChangeForm, NotificationSettingsForm
)
from .forms import SignUpWithPaymentForm
import json
import uuid
import logging

logger = logging.getLogger(__name__)



def home(request):
    """Landing page"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return render(request, 'accounts/home.html')


def signup_with_payment(request):
    """Single page signup with STK push payment"""

    # Get dynamic registration fee from database
    registration_fee = PlatformSettings.get_registration_fee()

    if request.method == 'POST':
        form = SignUpWithPaymentForm(request.POST)
        if form.is_valid():
            # Get and format phone number consistently
            phone_number = form.cleaned_data.get('phone_number', '')
            if not phone_number:
                messages.error(request, 'Phone number is required for M-Pesa payment.')
                return render(request, 'accounts/signup_with_payment.html', {
                    'form': form,
                    'registration_fee': registration_fee
                })

            # Format phone number once and use everywhere
            if phone_number.startswith('0'):
                formatted_phone = '254' + phone_number[1:]
            elif phone_number.startswith('+254'):
                formatted_phone = phone_number[1:]
            elif not phone_number.startswith('254'):
                formatted_phone = '254' + phone_number
            else:
                formatted_phone = phone_number

            # Check if user already exists BEFORE processing payment
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']

            if CustomUser.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists. Please choose a different username.')
                return render(request, 'accounts/signup_with_payment.html', {
                    'form': form,
                    'registration_fee': registration_fee
                })

            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, f'Email "{email}" already exists. Please use a different email.')
                return render(request, 'accounts/signup_with_payment.html', {
                    'form': form,
                    'registration_fee': registration_fee
                })

            if CustomUser.objects.filter(phone_number=formatted_phone).exists():
                messages.error(request, f'Phone number already registered. Please use a different number.')
                return render(request, 'accounts/signup_with_payment.html', {
                    'form': form,
                    'registration_fee': registration_fee
                })

            # Store user data in session with FORMATTED phone number
            request.session['signup_data'] = {
                'username': username,
                'email': email,
                'password': form.cleaned_data['password1'],
                'phone_number': formatted_phone,
                'first_name': form.cleaned_data.get('first_name', ''),
                'last_name': form.cleaned_data.get('last_name', ''),
            }

            # Check environment and process payment accordingly
            if settings.MPESA_ENVIRONMENT == 'sandbox':
                # For sandbox, initiate real STK push (but with test credentials)
                return initiate_stk_push_payment(request, formatted_phone, registration_fee)
            else:
                # Production mode - real M-Pesa request
                return initiate_stk_push_payment(request, formatted_phone, registration_fee)
    else:
        form = SignUpWithPaymentForm()

    return render(request, 'accounts/signup_with_payment.html', {
        'form': form,
        'registration_fee': registration_fee  # Changed from subscription_price
    })

def initiate_stk_push_payment(request, phone_number, registration_fee):
    """Initiate STK push payment for registration with dynamic pricing"""
    try:
        signup_data = request.session.get('signup_data')
        if not signup_data:
            messages.error(request, 'Session expired. Please try again.')
            return redirect('accounts:signup_with_payment')

        # Generate unique reference
        account_reference = f"REG-{uuid.uuid4().hex[:8].upper()}"

        # Create payment transaction record with DYNAMIC amount
        payment_transaction = SubscriptionPayment.objects.create(
            transaction_type='REGISTRATION',
            amount=registration_fee,  # Changed from settings.SUBSCRIPTION_PRICE
            phone_number=phone_number,
            account_reference=account_reference,
            transaction_desc='InvestorConnect Registration Fee',
            temp_email=signup_data['email'],
            temp_username=signup_data['username'],
            temp_user_type='regular',
            checkout_request_id=f'temp_{uuid.uuid4().hex}'
        )

        logger.info(f"Created payment transaction: {payment_transaction.id} for {signup_data['username']}")

        # Store transaction ID in session
        request.session['payment_transaction_id'] = str(payment_transaction.id)

        # Initialize M-Pesa service and send STK push with DYNAMIC amount
        mpesa_service = MpesaService()
        result = mpesa_service.stk_push(
            phone_number=phone_number,
            amount=int(registration_fee),  # Changed from settings.SUBSCRIPTION_PRICE, convert to int for M-Pesa
            account_reference=account_reference,
            transaction_desc='InvestorConnect Registration Fee'
        )

        if result['success']:
            # Update transaction with actual checkout request ID
            payment_transaction.checkout_request_id = result['checkout_request_id']
            payment_transaction.mpesa_transaction_id = result['merchant_request_id']
            payment_transaction.save()

            logger.info(f"STK push successful for transaction: {payment_transaction.id}")

            messages.success(request,
                             f'Payment request sent to {phone_number}. Please check your phone and enter your M-Pesa PIN.')

            return render(request, 'accounts/payment_pending_signup.html', {
                'phone_number': phone_number,
                'amount': registration_fee,  # Changed from settings.SUBSCRIPTION_PRICE
                'transaction_id': str(payment_transaction.id),
                'checkout_request_id': result['checkout_request_id']
            })
        else:
            # Mark transaction as failed
            payment_transaction.status = 'failed'
            payment_transaction.failure_reason = result['message']
            payment_transaction.save()

            logger.error(f"STK push failed for transaction: {payment_transaction.id} - {result['message']}")

            messages.error(request, f'Payment request failed: {result["message"]}. Please try again.')
            return render(request, 'accounts/signup_with_payment.html', {
                'form': SignUpWithPaymentForm(initial=signup_data),
                'registration_fee': registration_fee  # Changed from subscription_price
            })

    except Exception as e:
        logger.error(f"Error initiating STK push: {e}")
        messages.error(request, 'An error occurred while processing payment. Please try again.')
        return redirect('accounts:signup_with_payment')


# @csrf_exempt
# @require_http_methods(["POST"])
# def mpesa_callback(request):
#     """Handle M-Pesa callback for registration payments"""
#     try:
#         # Log the raw callback data
#         callback_body = request.body.decode('utf-8')
#         logger.info(f"M-Pesa callback received: {callback_body}")
#
#         callback_data = json.loads(callback_body)
#
#         # Extract callback data
#         stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
#         result_code = stk_callback.get('ResultCode')
#         checkout_request_id = stk_callback.get('CheckoutRequestID')
#         result_desc = stk_callback.get('ResultDesc', '')
#
#         logger.info(f"Processing callback for checkout_request_id: {checkout_request_id}, result_code: {result_code}")
#
#         # Find transaction
#         try:
#             payment_transaction = SubscriptionPayment.objects.get(
#                 checkout_request_id=checkout_request_id
#             )
#
#             if result_code == 0:  # Success
#                 payment_transaction.status = 'completed'
#
#                 # Extract receipt number and other metadata
#                 callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
#                 for item in callback_metadata:
#                     name = item.get('Name')
#                     value = item.get('Value')
#
#                     if name == 'MpesaReceiptNumber':
#                         payment_transaction.mpesa_receipt_number = value
#
#                 payment_transaction.save()
#
#                 logger.info(
#                     f"Payment transaction {payment_transaction.id} completed with receipt: {payment_transaction.mpesa_receipt_number}")
#
#                 # Create user account after successful payment
#                 if payment_transaction.transaction_type == 'REGISTRATION':
#                     create_user_from_payment_transaction(payment_transaction)
#
#             else:  # Failed or cancelled
#                 payment_transaction.status = 'failed'
#                 payment_transaction.failure_reason = result_desc
#                 payment_transaction.save()
#
#                 logger.warning(f"Payment transaction {payment_transaction.id} failed: {result_desc}")
#
#         except SubscriptionPayment.DoesNotExist:
#             logger.error(f"Payment transaction not found for checkout_request_id: {checkout_request_id}")
#
#     except json.JSONDecodeError as e:
#         logger.error(f"Invalid JSON in callback: {e}")
#     except Exception as e:
#         logger.error(f"Callback processing error: {e}")
#
#     # Always return success to M-Pesa to acknowledge receipt
#     return JsonResponse({
#         'ResultCode': 0,
#         'ResultDesc': 'Success'
#     })


def create_user_from_payment_transaction(payment_transaction):
    """Create user account after successful payment"""
    try:
        with transaction.atomic():
            # Create the user account
            user = CustomUser.objects.create(
                username=payment_transaction.temp_username,
                email=payment_transaction.temp_email,
                password=make_password('temp_password_will_be_reset'),  # User will reset this
                phone_number=payment_transaction.phone_number,
                user_type='regular',
                subscription_paid=True,
                is_verified=True,
            )

            # Update payment transaction with user
            payment_transaction.user = user
            payment_transaction.save()

            logger.info(f"User {user.username} created from payment transaction {payment_transaction.id}")

            # Create profile extension
            profile, created = UserProfileExtension.objects.get_or_create(user=user)
            logger.info(f"Profile extension {'created' if created else 'retrieved'}: {profile.id}")

            # Create notification settings with defaults
            notifications, created = NotificationSettings.objects.get_or_create(
                user=user,
                defaults={
                    'email_new_messages': True,
                    'email_pitch_interest': True,
                    'browser_new_messages': True,
                    'browser_pitch_updates': True,
                }
            )
            logger.info(f"Notification settings {'created' if created else 'retrieved'}: {notifications.id}")

            # Send welcome email (implement this function)
            send_welcome_email_with_login_instructions(user, payment_transaction)

    except Exception as e:
        logger.error(f"Error creating user from payment transaction {payment_transaction.id}: {e}")
        # Optionally, you could mark the payment as needing manual review
        payment_transaction.failure_reason = f"Account creation failed: {str(e)}"
        payment_transaction.save()


def send_welcome_email_with_login_instructions(user, payment_transaction):
    """Send welcome email with login instructions"""
    try:
        from django.core.mail import send_mail
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        # Generate password reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # Create reset link
        reset_link = f"https://bazuuconnect.com/accounts/reset/{uid}/{token}/"

        subject = 'Welcome to InvestorConnect - Set Your Password'
        message = f'''
Dear {user.username},

Welcome to InvestorConnect! Your registration payment of KES {payment_transaction.amount} has been successfully processed.

Payment Details:
- Receipt Number: {payment_transaction.mpesa_receipt_number}
- Transaction ID: {payment_transaction.id}
- Phone Number: {payment_transaction.phone_number}

To complete your registration and access your account, please set your password by clicking the link below:
{reset_link}

This link will expire in 24 hours for security reasons.

Thank you for joining our platform!

Best regards,
InvestorConnect Team
        '''

        # Send email
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        logger.info(f"Welcome email sent to {user.email}")

    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {e}")


def check_payment_status(request):
    """AJAX endpoint to check payment status"""
    transaction_id = request.GET.get('transaction_id')

    if not transaction_id:
        return JsonResponse({
            'status': 'ERROR',
            'message': 'Transaction ID is required'
        })

    try:
        payment_transaction = SubscriptionPayment.objects.get(id=transaction_id)

        response_data = {
            'status': payment_transaction.status,
            'transaction_id': str(payment_transaction.id),
            'amount': str(payment_transaction.amount),
            'phone_number': payment_transaction.phone_number
        }

        if payment_transaction.status == 'completed':
            response_data.update({
                'message': 'Payment completed successfully! Your account has been created.',
                'receipt_number': payment_transaction.mpesa_receipt_number,
                'redirect_url': '/accounts/login/',
                'success': True
            })
        elif payment_transaction.status == 'failed':
            response_data.update({
                'message': f'Payment failed: {payment_transaction.failure_reason}',
                'success': False
            })
        else:  # pending
            response_data.update({
                'message': 'Payment pending. Please check your phone for M-Pesa prompt.',
                'success': False
            })

        return JsonResponse(response_data)

    except SubscriptionPayment.DoesNotExist:
        return JsonResponse({
            'status': 'ERROR',
            'message': 'Transaction not found',
            'success': False
        })
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        return JsonResponse({
            'status': 'ERROR',
            'message': 'An error occurred while checking payment status',
            'success': False
        })


def simulate_payment_success(request):
    """Simulate successful payment for testing - Enhanced for real transactions"""
    if not settings.DEBUG:
        messages.error(request, 'This feature is only available in development.')
        return redirect('accounts:signup_with_payment')

    transaction_id = request.session.get('payment_transaction_id')
    if not transaction_id:
        messages.error(request, 'No payment transaction found. Please start the signup process again.')
        return redirect('accounts:signup_with_payment')

    try:
        payment_transaction = SubscriptionPayment.objects.get(id=transaction_id)

        # Simulate successful payment
        payment_transaction.status = 'completed'
        payment_transaction.mpesa_receipt_number = f'TEST{uuid.uuid4().hex[:8].upper()}'
        payment_transaction.save()

        # Create user account
        create_user_from_payment_transaction(payment_transaction)

        messages.success(request, 'Payment simulated successfully! Account created.')
        return redirect('accounts:login')

    except SubscriptionPayment.DoesNotExist:
        messages.error(request, 'Payment transaction not found.')
        return redirect('accounts:signup_with_payment')
    except Exception as e:
        logger.error(f"Error simulating payment: {e}")
        messages.error(request, f'Error simulating payment: {str(e)}')
        return redirect('accounts:signup_with_payment')


# Keep your original create_account_after_payment function as backup
def create_account_after_payment(request):
    """Legacy function - kept for backward compatibility"""
    # Your original implementation here...
    pass
@login_required
def dashboard(request):
    """Universal dashboard view for all user types"""
    user = request.user

    # Ensure profile extension exists
    profile_extension, created = UserProfileExtension.objects.get_or_create(user=user)

    # Ensure notification settings exist
    notification_settings, created = NotificationSettings.objects.get_or_create(
        user=user,
        defaults={
            'email_new_messages': True,
            'email_pitch_interest': True,
            'browser_new_messages': True,
            'browser_pitch_updates': True,
        }
    )

    context = {'user': user}

    # Admin dashboard
    if user.is_staff:
        try:
            from pitches.models import IdeaPitch
            context.update({
                'total_users': CustomUser.objects.count(),
                'total_investors': CustomUser.objects.filter(user_type='investor').count(),
                'total_entrepreneurs': CustomUser.objects.filter(user_type='regular').count(),
                'pending_pitches': IdeaPitch.objects.filter(status='pending').count(),
                'approved_pitches': IdeaPitch.objects.filter(status='approved').count(),
                'rejected_pitches': IdeaPitch.objects.filter(status='rejected').count(),
                'recent_signups': CustomUser.objects.order_by('-created_at')[:5],
                'recent_pitches': IdeaPitch.objects.order_by('-submitted_at')[:5],
            })
        except:
            context.update({
                'total_users': 0,
                'total_investors': 0,
                'total_entrepreneurs': 0,
                'pending_pitches': 0,
                'approved_pitches': 0,
                'rejected_pitches': 0,
                'recent_signups': [],
                'recent_pitches': [],
            })

        return render(request, 'accounts/admin_dashboard.html', context)

    elif user.is_investor:
        # Get investor-specific stats
        try:
            context.update({
                'total_pitches': IdeaPitch.objects.filter(status='approved').count(),
                'my_interests': getattr(user, 'investor_interests', user.pitchinterest_set).count(),
                'recent_pitches': IdeaPitch.objects.filter(status='approved').order_by('-submitted_at')[:5],
            })
        except:
            context.update({
                'total_pitches': 0,
                'my_interests': 0,
                'recent_pitches': [],
            })
    else:
        # Get entrepreneur-specific stats
        try:
            user_pitches = user.pitches.all()
            context.update({
                'my_pitches': user_pitches.count(),
                'approved_pitches': user_pitches.filter(status='approved').count(),
                'pending_pitches': user_pitches.filter(status='pending').count(),
                'rejected_pitches': user_pitches.filter(status='rejected').count(),
                'recent_pitches': user_pitches.order_by('-submitted_at')[:5],
            })
        except:
            context.update({
                'my_pitches': 0,
                'approved_pitches': 0,
                'pending_pitches': 0,
                'rejected_pitches': 0,
                'recent_pitches': [],
            })

    # Use single template for all users (except admins)
    return render(request, 'accounts/dashboard.html', context)

@login_required
def logout_view(request):
    """Log out user and update their online status"""
    # Update user activity to offline before logout
    try:
        from chat.models import UserActivity
        activity, created = UserActivity.objects.get_or_create(user=request.user)
        activity.is_online = False
        activity.is_typing = False
        activity.save()
    except Exception as e:
        pass  # Silent fail for chat functionality

    messages.success(request, "You have been logged out successfully.")
    logout(request)
    return redirect('accounts:home')


# PROFILE MANAGEMENT VIEWS

@login_required
def profile_view(request):
    """View current user's own profile"""
    # Get or create profile extension
    profile_extension, created = UserProfileExtension.objects.get_or_create(user=request.user)

    context = {
        'user': request.user,
        'profile_extension': profile_extension,
        'is_own_profile': True,
    }
    return render(request, 'accounts/profile_view.html', context)


@login_required
def profile_detail_view(request, username):
    """View any user's profile by username"""
    user = get_object_or_404(CustomUser, username=username)

    # Ensure user has access to platform
    if not user.can_access_platform:
        messages.error(request, "This user profile is not accessible.")
        return redirect('accounts:dashboard')

    # Get or create profile extension
    profile_extension, created = UserProfileExtension.objects.get_or_create(user=user)

    context = {
        'user': user,
        'profile_extension': profile_extension,
        'is_own_profile': request.user == user,
    }
    return render(request, 'accounts/profile_view.html', context)


@login_required
def profile_edit(request):
    """Edit user profile information - both main and extended"""
    profile_extension, created = UserProfileExtension.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = CustomUserProfileForm(request.POST, instance=request.user)
        profile_form = UserProfileExtensionForm(
            request.POST, request.FILES,
            instance=profile_extension,
            user=request.user
        )

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('accounts:profile_view')
        else:
            # Collect and display form errors
            errors = []
            for field, field_errors in user_form.errors.items():
                for error in field_errors:
                    errors.append(f'{field}: {error}')
            for field, field_errors in profile_form.errors.items():
                for error in field_errors:
                    errors.append(f'{field}: {error}')

            if errors:
                for error in errors:
                    messages.error(request, error)
            else:
                messages.error(request, 'Please correct the errors below.')
    else:
        user_form = CustomUserProfileForm(instance=request.user)
        profile_form = UserProfileExtensionForm(instance=profile_extension, user=request.user)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,  # Changed from extension_form to match template
        'profile_extension': profile_extension,
    }
    return render(request, 'accounts/profile_edit.html', context)


@login_required
def profile_settings_menu(request):
    """Main profile settings menu/dashboard"""
    profile_extension, created = UserProfileExtension.objects.get_or_create(user=request.user)
    notification_settings_obj, created = NotificationSettings.objects.get_or_create(user=request.user)

    # Calculate profile completion percentage
    completion_percentage = calculate_profile_completion(request.user, profile_extension)

    context = {
        'user': request.user,
        'profile_extension': profile_extension,
        'notification_settings': notification_settings_obj,
        'completion_percentage': completion_percentage,
    }
    return render(request, 'accounts/profile_settings_menu.html', context)


@login_required
def change_password(request):
    """Change user password"""
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Your password has been changed successfully!')
            return redirect('accounts:profile_settings_menu')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomPasswordChangeForm(request.user)

    context = {
        'form': form,
    }
    return render(request, 'accounts/change_password.html', context)


@login_required
def notification_settings(request):
    """Manage notification preferences"""
    settings_obj, created = NotificationSettings.objects.get_or_create(
        user=request.user,
        defaults={
            'email_new_messages': True,
            'email_pitch_interest': True,
            'browser_new_messages': True,
            'browser_pitch_updates': True,
        }
    )

    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Notification settings updated successfully!')
            return redirect('accounts:profile_settings_menu')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = NotificationSettingsForm(instance=settings_obj)

    context = {
        'form': form,
        'settings': settings_obj,
    }
    return render(request, 'accounts/notification_settings.html', context)


@login_required
@require_http_methods(["POST"])
def delete_profile_picture(request):
    """Delete user's profile picture via AJAX"""
    try:
        profile_extension = UserProfileExtension.objects.get(user=request.user)
        if profile_extension.profile_picture:
            # Delete the file from storage
            profile_extension.profile_picture.delete(save=False)
            profile_extension.profile_picture = None
            profile_extension.save()

            messages.success(request, 'Profile picture deleted successfully!')
            return JsonResponse({'success': True, 'message': 'Profile picture deleted successfully!'})
        else:
            return JsonResponse({'success': False, 'message': 'No profile picture to delete.'})
    except UserProfileExtension.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Profile extension not found.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})


def calculate_profile_completion(user, profile_extension):
    """Calculate what percentage of the profile is completed"""
    total_fields = 0
    completed_fields = 0

    # Check main user fields
    user_fields = {
        'username': user.username,
        'email': user.email,
        'phone_number': user.phone_number,
        'company_name': user.company_name,
        'profile_description': user.profile_description,
    }

    for field_name, field_value in user_fields.items():
        total_fields += 1
        if field_value and str(field_value).strip():
            completed_fields += 1

    # Check profile extension fields
    extension_fields = {
        'first_name': profile_extension.first_name,
        'last_name': profile_extension.last_name,
        'location': profile_extension.location,
        'job_title': profile_extension.job_title,
        'industry': profile_extension.industry,
        'experience_level': profile_extension.experience_level,
    }

    for field_name, field_value in extension_fields.items():
        total_fields += 1
        if field_value and str(field_value).strip():
            completed_fields += 1

    # Check profile picture
    total_fields += 1
    if profile_extension.profile_picture:
        completed_fields += 1

    # Check optional fields that add value
    optional_fields = {
        'website': profile_extension.website,
        'linkedin_url': profile_extension.linkedin_url,
    }

    for field_name, field_value in optional_fields.items():
        total_fields += 1
        if field_value and str(field_value).strip():
            completed_fields += 1

    # Add user-type specific fields
    if user.user_type == 'investor':
        total_fields += 2
        if profile_extension.investment_range:
            completed_fields += 1
        if profile_extension.investment_focus and str(profile_extension.investment_focus).strip():
            completed_fields += 1
    else:
        total_fields += 2
        if profile_extension.business_stage:
            completed_fields += 1
        if profile_extension.funding_goal and profile_extension.funding_goal > 0:
            completed_fields += 1

    # Calculate percentage
    if total_fields > 0:
        percentage = int((completed_fields / total_fields) * 100)
        return min(percentage, 100)  # Cap at 100%

    return 0


# HELPER FUNCTIONS

def get_user_stats(user):
    """Get user-specific statistics for dashboard"""
    if user.is_investor:
        return {
            'total_pitches': IdeaPitch.objects.filter(status='approved').count(),
            'my_interests': user.pitchinterest_set.count() if hasattr(user, 'pitchinterest_set') else 0,
            'messages_count': 0,  # TODO: Implement when chat is ready
        }
    else:
        user_pitches = user.pitches.all() if hasattr(user, 'pitches') else IdeaPitch.objects.none()
        return {
            'total_pitches': user_pitches.count(),
            'approved_pitches': user_pitches.filter(status='approved').count(),
            'pending_pitches': user_pitches.filter(status='pending').count(),
            'rejected_pitches': user_pitches.filter(status='rejected').count(),
        }


# In accounts/views.py
@login_required
def contact_admin(request):
    """Start a chat with any available admin"""
    # Get the first available admin (you could make this more sophisticated)
    admin_user = CustomUser.objects.filter(is_staff=True, is_active=True).first()

    if not admin_user:
        messages.error(request, "No administrators are currently available.")
        return redirect('accounts:dashboard')

    return redirect('chat:start_chat', username=admin_user.username)