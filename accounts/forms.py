from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import CustomUser, UserProfileExtension, NotificationSettings


class SignUpWithPaymentForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=True, help_text="Required for M-Pesa payment")

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2', 'phone_number')

    def clean_username(self):
        username = self.cleaned_data['username']
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")
        return email


class CustomUserProfileForm(forms.ModelForm):
    """Form for editing main user profile information - username/email disabled"""

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'profile_description', 'phone_number']  # Added username and email back

        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm bg-gray-100 cursor-not-allowed',
                'readonly': True,
                'disabled': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm bg-gray-100 cursor-not-allowed',
                'readonly': True,
                'disabled': True
            }),
            'profile_description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Tell us about yourself...',
                'rows': 4
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '+1234567890'
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Make username and email fields non-editable
        if 'username' in self.fields:
            self.fields['username'].disabled = True
            self.fields['username'].required = False

        if 'email' in self.fields:
            self.fields['email'].disabled = True
            self.fields['email'].required = False

        # For investors only, add company_name field (admin-only visibility)
        if user and user.is_investor:
            self.fields['company_name'] = forms.CharField(
                max_length=100,
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                    'placeholder': 'Company Name'
                })
            )
            self.fields['company_name'].initial = user.company_name

    def save(self, commit=True):
        """Override save to prevent username/email changes"""
        instance = super().save(commit=False)

        # Ensure username and email are not changed
        if self.instance.pk:
            original = CustomUser.objects.get(pk=self.instance.pk)
            instance.username = original.username
            instance.email = original.email

        if commit:
            instance.save()
        return instance


class UserProfileExtensionForm(forms.ModelForm):
    """Form for extended profile information - privacy focused"""

    class Meta:
        model = UserProfileExtension
        fields = [
            'first_name', 'last_name', 'profile_picture', 'location',
            'job_title', 'industry', 'experience_level',
            'investment_range', 'investment_focus',
            'business_stage', 'funding_goal',
            'profile_visibility'
        ]
        # Removed: 'website', 'linkedin_url', 'show_email', 'show_phone'

        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Last Name'
            }),
            'profile_picture': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
            'location': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'City, Country'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Job Title'
            }),
            'industry': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'experience_level': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'investment_range': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'investment_focus': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'business_stage': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'funding_goal': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '50000'
            }),
            'profile_visibility': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            })
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            # For admin users, keep only profile_picture
            if user.is_staff:
                fields_to_keep = ['profile_picture']
                fields_to_remove = [field for field in self.fields.keys() if field not in fields_to_keep]
                for field in fields_to_remove:
                    self.fields.pop(field, None)
            else:
                # Regular user logic
                # Hide investor-specific fields for entrepreneurs
                if not user.is_investor:
                    self.fields.pop('investment_range', None)
                    self.fields.pop('investment_focus', None)

                # Hide entrepreneur-specific fields for investors
                if user.is_investor:
                    self.fields.pop('business_stage', None)
                    self.fields.pop('funding_goal', None)

    def save(self, commit=True):
        """Override save to handle admin users properly"""
        instance = super().save(commit=False)

        # For admin users, ensure profile_visibility has a default value
        if hasattr(self.instance, 'user') and self.instance.user.is_staff:
            if not instance.profile_visibility:
                instance.profile_visibility = 'members'

        if commit:
            instance.save()
        return instance


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with styled fields"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Style all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            })


class NotificationSettingsForm(forms.ModelForm):
    """Form for notification preferences"""

    class Meta:
        model = NotificationSettings
        fields = [
            'email_new_messages', 'email_pitch_interest', 'email_pitch_approved',
            'email_weekly_digest', 'browser_new_messages', 'browser_pitch_updates',
            'sms_critical_updates'
        ]

        widgets = {
            'email_new_messages': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            }),
            'email_pitch_interest': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            }),
            'email_pitch_approved': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            }),
            'email_weekly_digest': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            }),
            'browser_new_messages': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            }),
            'browser_pitch_updates': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            }),
            'sms_critical_updates': forms.CheckboxInput(attrs={
                'class': 'rounded text-blue-600 focus:ring-blue-500'
            })
        }