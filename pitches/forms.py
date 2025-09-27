# pitches/forms.py - Complete updated version with file upload support
from django import forms
from .models import IdeaPitch, PitchCategory, PitchFile, InvestorPost


class PitchForm(forms.ModelForm):
    class Meta:
        model = IdeaPitch
        fields = ['title', 'description', 'category', 'budget_required', 'timeline']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter your pitch title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'rows': 5,
                'placeholder': 'Describe your business idea in detail'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'budget_required': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter budget amount in KES (optional)'
            }),
            'timeline': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g., 6 months, 1 year (optional)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make title, description, and category required
        self.fields['title'].required = True
        self.fields['description'].required = True
        self.fields['category'].required = True
        # Budget and timeline are optional
        self.fields['budget_required'].required = False
        self.fields['timeline'].required = False


class PitchFileForm(forms.ModelForm):
    class Meta:
        model = PitchFile
        fields = ['file', 'file_type', 'description']  # Remove 'is_public' from here
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none',
                'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png,.ppt,.pptx,.xls,.xlsx'
            }),
            'file_type': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'description': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Brief description of this file (optional)'
            }),
            # Remove the is_public widget too
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (10MB limit)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size cannot exceed 10MB.')

            # Check file extension
            allowed_extensions = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'ppt', 'pptx', 'xls', 'xlsx']
            file_extension = file.name.split('.')[-1].lower()
            if file_extension not in allowed_extensions:
                raise forms.ValidationError(f'File type .{file_extension} is not allowed.')

        return file

class InvestorPostForm(forms.ModelForm):
    class Meta:
        model = InvestorPost
        fields = ['title', 'content', 'featured_image', 'tags']  # Remove 'post_type'
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter testimonial title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 8,
                'placeholder': 'Share your testimonial or experience...'
            }),
            'featured_image': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50',
                'accept': 'image/*'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'e.g., startup, success, experience (comma-separated)'
            }),
        }