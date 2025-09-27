# accounts/views.py - COMPLETE UPDATED VERSION

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .forms import SignUpWithPaymentForm
from .models import CustomUser, UserProfileExtension, NotificationSettings
from payments.models import SubscriptionPayment
from django.conf import settings
from pitches.models import IdeaPitch
from django.shortcuts import render, redirect, get_object_or_404

# Profile management form imports
from .forms import (
    CustomUserProfileForm, UserProfileExtensionForm,
    CustomPasswordChangeForm, NotificationSettingsForm
)


def home(request):
    """Landing page"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    return render(request, 'accounts/home.html')


def signup_with_payment(request):
    """Single page signup with payment"""
    if request.method == 'POST':
        form = SignUpWithPaymentForm(request.POST)
        if form.is_valid():
            # Get and format phone number consistently
            phone_number = form.cleaned_data.get('phone_number', '')
            if not phone_number:
                messages.error(request, 'Phone number is required for M-Pesa payment.')
                return render(request, 'accounts/signup_with_payment.html', {'form': form})

            # Format phone number once and use everywhere
            if phone_number.startswith('0'):
                formatted_phone = '254' + phone_number[1:]
            elif phone_number.startswith('+254'):
                formatted_phone = phone_number[1:]
            elif not phone_number.startswith('254'):
                formatted_phone = '254' + phone_number
            else:
                formatted_phone = phone_number

            # Store user data in session with FORMATTED phone number
            request.session['signup_data'] = {
                'username': form.cleaned_data['username'],
                'email': form.cleaned_data['email'],
                'password': form.cleaned_data['password1'],
                'phone_number': formatted_phone,  # Use formatted version consistently
            }

            # Store payment info in session (same formatted number)
            request.session['payment_phone'] = formatted_phone

            messages.success(request,
                             f'Payment request sent to {formatted_phone}. Please complete M-Pesa payment to create your account.')
            return render(request, 'accounts/payment_pending_signup.html', {
                'phone_number': formatted_phone,
                'amount': settings.SUBSCRIPTION_PRICE
            })
    else:
        form = SignUpWithPaymentForm()

    return render(request, 'accounts/signup_with_payment.html', {
        'form': form,
        'subscription_price': settings.SUBSCRIPTION_PRICE
    })


def create_account_after_payment(request):
    """Called after successful payment to create the actual account"""
    signup_data = request.session.get('signup_data')
    if not signup_data:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('accounts:signup')

    try:
        with transaction.atomic():
            # Debug: Print session data
            print(f"DEBUG: Session data: {signup_data}")

            # Check for existing users BEFORE creating
            username = signup_data['username']
            email = signup_data['email']
            phone_number = signup_data.get('phone_number', '')

            # Check for conflicts
            existing_username = CustomUser.objects.filter(username=username).exists()
            existing_email = CustomUser.objects.filter(email=email).exists()
            existing_phone = CustomUser.objects.filter(phone_number=phone_number).exists() if phone_number else False

            if existing_username:
                messages.error(request, f'Username "{username}" already exists. Please choose a different username.')
                return redirect('accounts:signup')

            if existing_email:
                messages.error(request, f'Email "{email}" already exists. Please use a different email.')
                return redirect('accounts:signup')

            if existing_phone:
                messages.error(request,
                               f'Phone number "{phone_number}" already exists. Please use a different phone number.')
                return redirect('accounts:signup')

            # Create the user account
            user = CustomUser.objects.create(
                username=username,
                email=email,
                password=make_password(signup_data['password']),
                phone_number=phone_number,
                user_type='regular',
                subscription_paid=True,
                is_verified=True,
            )
            print(f"DEBUG: User created successfully: {user.id}")

            # Create profile extension (use get_or_create to avoid conflicts)
            profile, created = UserProfileExtension.objects.get_or_create(user=user)
            print(f"DEBUG: Profile extension {'created' if created else 'retrieved'}: {profile.id}")

            # Create notification settings with defaults (use get_or_create to avoid conflicts)
            notifications, created = NotificationSettings.objects.get_or_create(
                user=user,
                defaults={
                    'email_new_messages': True,
                    'email_pitch_interest': True,
                    'browser_new_messages': True,
                    'browser_pitch_updates': True,
                }
            )
            print(f"DEBUG: Notification settings {'created' if created else 'retrieved'}: {notifications.id}")

            # Clear session data
            del request.session['signup_data']
            if 'payment_phone' in request.session:
                del request.session['payment_phone']

            # Log the user in
            login(request, user)
            messages.success(request, 'Account created and verified successfully! Welcome to InvestorConnect.')
            return redirect('accounts:dashboard')

    except Exception as e:
        # Print detailed error information
        print(f"ERROR: Account creation failed: {str(e)}")
        print(f"ERROR TYPE: {type(e).__name__}")

        # Print full traceback
        import traceback
        traceback.print_exc()

        # Check specific common errors
        if 'UNIQUE constraint failed' in str(e):
            if 'username' in str(e):
                messages.error(request, f'Username "{username}" already exists. Please choose a different username.')
            elif 'email' in str(e):
                messages.error(request, f'Email "{email}" already exists. Please use a different email.')
            elif 'phone_number' in str(e):
                messages.error(request,
                               f'Phone number "{phone_number}" already exists. Please use a different phone number.')
            else:
                messages.error(request, 'An account with this information already exists.')
        else:
            messages.error(request, f'Error creating account: {str(e)}. Please contact support.')

        return redirect('accounts:signup')


def simulate_payment_success(request):
    """Simulate successful payment for testing - REMOVE IN PRODUCTION"""
    if not settings.DEBUG:
        messages.error(request, 'This feature is only available in development.')
        return redirect('accounts:signup')

    signup_data = request.session.get('signup_data')
    if not signup_data:
        messages.error(request, 'No signup data found. Please start the signup process again.')
        return redirect('accounts:signup')

    # Create the account after "successful payment"
    return create_account_after_payment(request)


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