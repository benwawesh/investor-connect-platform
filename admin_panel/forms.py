from django import forms
from django.contrib.auth.forms import UserCreationForm
from accounts.models import CustomUser
from pitches.models import IdeaPitch, PitchCategory


class CategoryForm(forms.ModelForm):
    class Meta:
        model = PitchCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Category name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'rows': 3,
                'placeholder': 'Category description'
            }),
        }


class InvestorRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    company_name = forms.CharField(max_length=200, required=False)
    profile_description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False
    )
    phone_number = forms.CharField(max_length=20, required=False)

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'password1',
                  'password2', 'company_name', 'profile_description', 'phone_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.company_name = self.cleaned_data.get('company_name')
        user.profile_description = self.cleaned_data.get('profile_description')
        user.phone_number = self.cleaned_data.get('phone_number')
        if commit:
            user.save()
        return user


class PitchReviewForm(forms.ModelForm):
    class Meta:
        model = IdeaPitch
        fields = ['status', 'admin_notes']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'admin_notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'rows': 4,
                'placeholder': 'Add notes for this review...'
            }),
        }