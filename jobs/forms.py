from django import forms
from django.utils import timezone
from .models import JobPosting, JobApplication, JobAlert, JobSavedJob


class JobPostingForm(forms.ModelForm):
    """Form for creating and editing job postings"""

    class Meta:
        model = JobPosting
        fields = [
            'title', 'description', 'requirements', 'responsibilities',
            'company_name', 'company_description', 'location', 'remote_ok',
            'job_type', 'industry', 'experience_level', 'salary_min', 'salary_max',
            'salary_currency', 'equity_offered', 'skills_required', 'benefits',
            'application_deadline'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'requirements': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'responsibilities': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'company_description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'skills_required': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'e.g., Python, Django, PostgreSQL, Git'
            }),
            'benefits': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'application_deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'e.g., Nairobi, Kenya or Remote'}),
            'salary_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'salary_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '1000'}),
            'salary_currency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'KES'}),
            'job_type': forms.Select(attrs={'class': 'form-control'}),
            'industry': forms.Select(attrs={'class': 'form-control'}),
            'experience_level': forms.Select(attrs={'class': 'form-control'}),
            'remote_ok': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'equity_offered': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set help texts
        self.fields['title'].help_text = "Be specific and clear about the role"
        self.fields['location'].help_text = "City, Country or 'Remote' for remote positions"
        self.fields['skills_required'].help_text = "List required skills separated by commas"
        self.fields['salary_min'].help_text = "Minimum salary (optional)"
        self.fields['salary_max'].help_text = "Maximum salary (optional)"
        self.fields['application_deadline'].help_text = "When should applications close?"

    def clean(self):
        cleaned_data = super().clean()
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')
        application_deadline = cleaned_data.get('application_deadline')

        # Validate salary range
        if salary_min and salary_max and salary_min > salary_max:
            raise forms.ValidationError("Minimum salary cannot be higher than maximum salary.")

        # Validate application deadline
        if application_deadline and application_deadline <= timezone.now():
            raise forms.ValidationError("Application deadline must be in the future.")

        return cleaned_data


class JobApplicationForm(forms.ModelForm):
    """Form for job applications"""

    class Meta:
        model = JobApplication
        fields = ['cover_letter', 'custom_resume', 'portfolio_links']
        widgets = {
            'cover_letter': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control',
                'placeholder': 'Write a compelling cover letter explaining why you\'re perfect for this role...'
            }),
            'custom_resume': forms.FileInput(attrs={'class': 'form-control'}),
            'portfolio_links': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Add links to your portfolio, GitHub, or relevant work (one per line)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields[
            'cover_letter'].help_text = "Explain why you're interested in this role and what makes you a great fit"
        self.fields[
            'custom_resume'].help_text = "Upload a custom resume for this application (optional - your profile resume will be used if not provided)"
        self.fields['portfolio_links'].help_text = "Additional links to showcase your work"

        # Make cover letter required
        self.fields['cover_letter'].required = True


class JobSearchForm(forms.Form):
    """Form for searching and filtering jobs"""

    keywords = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Job title, skills, or company name...'
        })
    )

    location = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City, country, or remote'
        })
    )

    job_type = forms.ChoiceField(
        choices=[('', 'Any Type')] + JobPosting.JOB_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    experience_level = forms.ChoiceField(
        choices=[('', 'Any Level')] + JobPosting.EXPERIENCE_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    industry = forms.ChoiceField(
        choices=[('', 'Any Industry')] + JobPosting.INDUSTRY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    remote_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    salary_min = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum salary',
            'step': '1000'
        })
    )


class JobAlertForm(forms.ModelForm):
    """Form for creating job alerts"""

    class Meta:
        model = JobAlert
        fields = [
            'title', 'keywords', 'location', 'remote_only', 'job_type',
            'experience_level', 'industry', 'salary_min', 'frequency'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Python Developer Jobs in Nairobi'
            }),
            'keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'python, django, backend'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nairobi, Kenya'
            }),
            'remote_only': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'job_type': forms.Select(attrs={'class': 'form-control'}),
            'experience_level': forms.Select(attrs={'class': 'form-control'}),
            'industry': forms.Select(attrs={'class': 'form-control'}),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'salary_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1000'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add empty choices for optional fields
        self.fields['job_type'].choices = [('', 'Any Type')] + list(self.fields['job_type'].choices)
        self.fields['experience_level'].choices = [('', 'Any Level')] + list(self.fields['experience_level'].choices)
        self.fields['industry'].choices = [('', 'Any Industry')] + list(self.fields['industry'].choices)

        # Set help texts
        self.fields['title'].help_text = "Give your job alert a descriptive name"
        self.fields['keywords'].help_text = "Keywords to search for in job titles and descriptions"
        self.fields['salary_min'].help_text = "Minimum salary threshold"


class SavedJobNotesForm(forms.ModelForm):
    """Form for updating notes on saved jobs"""

    class Meta:
        model = JobSavedJob
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Add personal notes about this job...'
            })
        }


class ApplicationStatusUpdateForm(forms.ModelForm):
    """Form for employers to update application status"""

    class Meta:
        model = JobApplication
        fields = ['status', 'status_notes', 'interview_scheduled_at', 'interview_location']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'status_notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Internal notes about this status change...'
            }),
            'interview_scheduled_at': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'interview_location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Office address or video call link'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Hide interview fields initially - can be shown with JavaScript based on status
        self.fields['interview_scheduled_at'].required = False
        self.fields['interview_location'].required = False