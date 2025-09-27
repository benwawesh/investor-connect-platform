from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.core.validators import RegexValidator
from django.utils import timezone


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ('investor', 'Investor'),
        ('regular', 'Regular User'),
        ('job_seeker', 'Job Seeker'),  # New user type added
    ]

    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('banned', 'Banned'),
    ]

    user_type = models.CharField(max_length=15, choices=USER_TYPE_CHOICES)  # Increased max_length
    is_verified = models.BooleanField(default=False)
    subscription_paid = models.BooleanField(default=False)
    profile_description = models.TextField(blank=True, null=True)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # User management fields
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='active')
    suspended_until = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

    @property
    def is_investor(self):
        return self.user_type == 'investor'

    @property
    def is_regular_user(self):
        return self.user_type == 'regular'

    @property
    def is_job_seeker(self):
        """Both regular users and job_seeker types can apply for jobs"""
        return self.user_type in ['regular', 'job_seeker']

    @property
    def is_suspended(self):
        """Check if user is currently suspended"""
        from django.utils import timezone
        if self.account_status == 'suspended':
            if self.suspended_until and timezone.now() > self.suspended_until:
                # Auto-unsuspend if suspension period expired
                self.account_status = 'active'
                self.suspended_until = None
                self.suspension_reason = None
                self.save()
                return False
            return True
        return False

    @property
    def can_access_platform(self):
        # Check if account is suspended first
        if self.is_suspended:
            return False

        # Staff and superusers always have platform access (unless suspended)
        if self.is_staff or self.is_superuser:
            return True

        if self.is_investor:
            return self.is_verified
        elif self.is_job_seeker:
            return self.is_verified
        return self.is_verified and self.subscription_paid

    @property
    def can_post_jobs(self):
        """Only admins/staff can post jobs"""
        if self.is_suspended:
            return False
        return self.is_staff or self.is_superuser

    @property
    def can_apply_for_jobs(self):
        """Regular users and job seekers can apply for jobs"""
        if self.is_suspended:
            return False
        return self.is_job_seeker and self.can_access_platform

    @property
    def can_create_investor_posts(self):
        """Investors and admin staff can create investor posts/insights"""
        if self.is_suspended:
            return False
        return self.is_investor or self.is_staff or self.is_superuser

    def suspend_account(self, duration_days=7, reason="Administrative action"):
        """Suspend user account for specified duration"""
        from django.utils import timezone
        from datetime import timedelta

        self.account_status = 'suspended'
        self.suspended_until = timezone.now() + timedelta(days=duration_days)
        self.suspension_reason = reason
        self.save()

    def unsuspend_account(self):
        """Remove suspension from user account"""
        self.account_status = 'active'
        self.suspended_until = None
        self.suspension_reason = None
        self.save()

    def get_suspension_info(self):
        """Get detailed suspension information"""
        if self.is_suspended:
            return {
                'is_suspended': True,
                'until': self.suspended_until,
                'reason': self.suspension_reason,
                'days_remaining': (self.suspended_until - timezone.now()).days if self.suspended_until else None
            }
        return {'is_suspended': False}


# Your existing UserProfileExtension model with job seeker enhancements
class UserProfileExtension(models.Model):
    """Extended profile information for users"""

    INDUSTRY_CHOICES = [
        ('technology', 'Technology'),
        ('healthcare', 'Healthcare'),
        ('finance', 'Finance'),
        ('retail', 'Retail'),
        ('manufacturing', 'Manufacturing'),
        ('education', 'Education'),
        ('real_estate', 'Real Estate'),
        ('agriculture', 'Agriculture'),
        ('entertainment', 'Entertainment'),
        ('other', 'Other'),
    ]

    INVESTMENT_RANGE_CHOICES = [
        ('under_10k', 'Under $10,000'),
        ('10k_50k', '$10,000 - $50,000'),
        ('50k_100k', '$50,000 - $100,000'),
        ('100k_500k', '$100,000 - $500,000'),
        ('500k_1m', '$500,000 - $1,000,000'),
        ('over_1m', 'Over $1,000,000'),
    ]

    EXPERIENCE_CHOICES = [
        ('beginner', 'Beginner (0-1 years)'),
        ('intermediate', 'Intermediate (2-5 years)'),
        ('experienced', 'Experienced (6-10 years)'),
        ('expert', 'Expert (10+ years)'),
    ]

    BUSINESS_STAGE_CHOICES = [
        ('idea', 'Idea Stage'),
        ('concept', 'Concept Development'),
        ('mvp', 'MVP/Prototype'),
        ('early', 'Early Stage/Launch'),
        ('growth', 'Growth Stage'),
        ('expansion', 'Expansion Stage'),
        ('mature', 'Mature Business'),
        ('pivot', 'Pivoting'),
    ]

    INVESTMENT_FOCUS_CHOICES = [
        ('early_stage', 'Early Stage Startups'),
        ('growth_stage', 'Growth Stage Companies'),
        ('tech_focused', 'Technology Focused'),
        ('social_impact', 'Social Impact'),
        ('local_business', 'Local Businesses'),
        ('diversified', 'Diversified Portfolio'),
    ]

    # NEW: Job Seeker specific choices
    JOB_LEVEL_CHOICES = [
        ('entry', 'Entry Level (0-2 years)'),
        ('junior', 'Junior (2-4 years)'),
        ('mid', 'Mid Level (4-7 years)'),
        ('senior', 'Senior Level (7-10 years)'),
        ('lead', 'Lead/Principal (10+ years)'),
        ('executive', 'Executive Level'),
    ]

    AVAILABILITY_CHOICES = [
        ('immediate', 'Available Immediately'),
        ('2_weeks', 'Two Weeks Notice'),
        ('1_month', 'One Month'),
        ('flexible', 'Flexible'),
    ]

    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
        ('any', 'Any'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='userprofileextension')

    # Personal Information
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, help_text="City, Country")

    # Professional Information
    job_title = models.CharField(max_length=100, blank=True)
    industry = models.CharField(max_length=20, choices=INDUSTRY_CHOICES, blank=True)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_CHOICES, blank=True)

    # Investor-specific fields
    investment_range = models.CharField(max_length=20, choices=INVESTMENT_RANGE_CHOICES, blank=True)
    investment_focus = models.CharField(max_length=20, choices=INVESTMENT_FOCUS_CHOICES, blank=True)

    # Entrepreneur-specific fields
    business_stage = models.CharField(
        max_length=20,
        choices=BUSINESS_STAGE_CHOICES,
        blank=True,
        help_text="Current stage of your business"
    )
    funding_goal = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    # NEW: Job Seeker specific fields
    resume = models.FileField(upload_to='resumes/', blank=True, null=True,
                              help_text="Upload your resume (PDF preferred)")
    skills = models.TextField(blank=True, help_text="List your key skills (comma-separated)")
    job_level = models.CharField(max_length=20, choices=JOB_LEVEL_CHOICES, blank=True)
    desired_salary_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                             help_text="Minimum desired salary")
    desired_salary_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                             help_text="Maximum desired salary")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, blank=True)
    preferred_employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    portfolio_url = models.URLField(blank=True, null=True, help_text="Link to your portfolio or personal website")
    linkedin_url = models.URLField(blank=True, null=True, help_text="Your LinkedIn profile URL")
    github_url = models.URLField(blank=True, null=True, help_text="Your GitHub profile (for tech roles)")
    open_to_remote = models.BooleanField(default=True, help_text="Open to remote work opportunities")
    preferred_locations = models.TextField(blank=True, help_text="Preferred work locations (one per line)")

    # Privacy Settings
    profile_visibility = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public'),
            ('members', 'Members Only'),
            ('private', 'Private'),
        ],
        default='members'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Extended Profile"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.user.username

    def get_display_name(self):
        if self.first_name or self.last_name:
            return self.get_full_name()
        return self.user.username

    def get_skills_list(self):
        """Return skills as a list"""
        if self.skills:
            return [skill.strip() for skill in self.skills.split(',') if skill.strip()]
        return []


class NotificationSettings(models.Model):
    """User notification preferences"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='notification_settings')

    # Email Notifications
    email_new_messages = models.BooleanField(default=True, help_text="Email when you receive new messages")
    email_pitch_interest = models.BooleanField(default=True,
                                               help_text="Email when someone shows interest in your pitch")
    email_pitch_approved = models.BooleanField(default=True, help_text="Email when your pitch is approved")
    email_weekly_digest = models.BooleanField(default=True, help_text="Weekly summary of platform activity")

    # NEW: Job-related email notifications
    email_job_matches = models.BooleanField(default=True, help_text="Email when new jobs match your profile")
    email_application_updates = models.BooleanField(default=True, help_text="Email when application status changes")
    email_new_applications = models.BooleanField(default=True,
                                                 help_text="Email when someone applies to your job posting")

    # Browser Notifications
    browser_new_messages = models.BooleanField(default=True)
    browser_pitch_updates = models.BooleanField(default=True)
    browser_job_alerts = models.BooleanField(default=True, help_text="Browser notifications for job-related activities")

    # SMS Notifications
    sms_critical_updates = models.BooleanField(default=False, help_text="SMS for important account updates")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Notification Settings"

