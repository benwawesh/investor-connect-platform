from django.db import models
from accounts.models import CustomUser
import uuid


class JobPosting(models.Model):
    """Job postings created by investors and entrepreneurs"""

    JOB_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('freelance', 'Freelance'),
        ('internship', 'Internship'),
    ]

    EXPERIENCE_LEVEL_CHOICES = [
        ('entry', 'Entry Level (0-2 years)'),
        ('junior', 'Junior (2-4 years)'),
        ('mid', 'Mid Level (4-7 years)'),
        ('senior', 'Senior Level (7-10 years)'),
        ('lead', 'Lead/Principal (10+ years)'),
        ('executive', 'Executive Level'),
    ]

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Job posting details
    title = models.CharField(max_length=200, help_text="Job title/position")
    description = models.TextField(help_text="Detailed job description")
    requirements = models.TextField(help_text="Required skills and qualifications")
    responsibilities = models.TextField(blank=True, help_text="Key responsibilities (optional)")

    # Company information
    poster = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='job_postings')
    company_name = models.CharField(max_length=200, help_text="Company or startup name")
    company_description = models.TextField(blank=True, help_text="Brief company description")

    # Job specifics
    location = models.CharField(max_length=200, help_text="Job location")
    remote_ok = models.BooleanField(default=False, help_text="Remote work allowed")
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='full_time')
    industry = models.CharField(max_length=20, choices=INDUSTRY_CHOICES)
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVEL_CHOICES)

    # Compensation
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                     help_text="Minimum salary (optional)")
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                     help_text="Maximum salary (optional)")
    salary_currency = models.CharField(max_length=3, default='KES', help_text="Currency code (KES, USD, etc.)")
    equity_offered = models.BooleanField(default=False, help_text="Equity/stock options available")

    # Additional details
    skills_required = models.TextField(help_text="Required skills (comma-separated)")
    benefits = models.TextField(blank=True, help_text="Benefits and perks offered")
    application_deadline = models.DateTimeField(blank=True, null=True, help_text="Application deadline")

    # Status and meta
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text="Featured job posting")
    views_count = models.PositiveIntegerField(default=0)
    applications_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at']),
            models.Index(fields=['industry', 'experience_level']),
            models.Index(fields=['location', 'remote_ok']),
        ]

    def __str__(self):
        return f"{self.title} at {self.company_name}"

    def get_salary_range(self):
        """Return formatted salary range"""
        if self.salary_min and self.salary_max:
            return f"{self.salary_currency} {self.salary_min:,.0f} - {self.salary_max:,.0f}"
        elif self.salary_min:
            return f"{self.salary_currency} {self.salary_min:,.0f}+"
        elif self.salary_max:
            return f"Up to {self.salary_currency} {self.salary_max:,.0f}"
        return "Salary not specified"

    def get_skills_list(self):
        """Return required skills as a list"""
        if self.skills_required:
            return [skill.strip() for skill in self.skills_required.split(',') if skill.strip()]
        return []

    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])

    def is_deadline_passed(self):
        """Check if application deadline has passed"""
        if self.application_deadline:
            from django.utils import timezone
            return timezone.now() > self.application_deadline
        return False


class JobApplication(models.Model):
    """Job applications submitted by regular users and job seekers"""

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('interview_completed', 'Interview Completed'),
        ('offer_made', 'Offer Made'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
        ('hired', 'Hired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Application relationships
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    # UPDATED: Allow both regular users and job seekers to apply
    applicant = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='job_applications',
                                  limit_choices_to={'user_type__in': ['regular', 'job_seeker']})

    # Application content
    cover_letter = models.TextField(help_text="Cover letter or application message")
    custom_resume = models.FileField(upload_to='job_applications/', blank=True, null=True,
                                     help_text="Upload a custom resume for this application")
    portfolio_links = models.TextField(blank=True, help_text="Additional portfolio links (one per line)")

    # Application status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    status_updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True,
                                          related_name='application_status_updates')
    status_notes = models.TextField(blank=True, help_text="Internal notes about status change")

    # Interview details (if applicable)
    interview_scheduled_at = models.DateTimeField(blank=True, null=True)
    interview_location = models.CharField(max_length=200, blank=True, help_text="Interview location or video link")
    interview_notes = models.TextField(blank=True, help_text="Interview feedback and notes")

    # Timestamps
    applied_at = models.DateTimeField(auto_now_add=True)
    status_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_at']
        unique_together = ['job_posting', 'applicant']  # Prevent duplicate applications
        indexes = [
            models.Index(fields=['applicant', '-applied_at']),
            models.Index(fields=['job_posting', 'status']),
            models.Index(fields=['status', '-applied_at']),
        ]

    def __str__(self):
        return f"{self.applicant.username} applied for {self.job_posting.title}"

    def update_status(self, new_status, updated_by=None, notes=""):
        """Update application status with tracking"""
        old_status = self.status
        self.status = new_status
        self.status_updated_by = updated_by
        self.status_notes = notes
        self.save(update_fields=['status', 'status_updated_by', 'status_notes', 'status_updated_at'])

        # Create status change notification (implement later with notifications)
        # self.create_status_notification(old_status, new_status)

    def get_resume_file(self):
        """Return the resume file to use (custom or profile resume)"""
        if self.custom_resume:
            return self.custom_resume
        elif hasattr(self.applicant, 'userprofileextension') and self.applicant.userprofileextension.resume:
            return self.applicant.userprofileextension.resume
        return None

    def get_portfolio_links_list(self):
        """Return portfolio links as a list"""
        if self.portfolio_links:
            return [link.strip() for link in self.portfolio_links.split('\n') if link.strip()]
        return []


class JobSavedJob(models.Model):
    """Jobs saved/bookmarked by regular users and job seekers"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # UPDATED: Allow both regular users and job seekers to save jobs
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_jobs',
                             limit_choices_to={'user_type__in': ['regular', 'job_seeker']})
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Personal notes about this job")

    class Meta:
        unique_together = ['user', 'job_posting']
        ordering = ['-saved_at']
        verbose_name = "Saved Job"
        verbose_name_plural = "Saved Jobs"

    def __str__(self):
        return f"{self.user.username} saved {self.job_posting.title}"


class JobAlert(models.Model):
    """Job alerts/notifications for regular users and job seekers"""

    FREQUENCY_CHOICES = [
        ('immediate', 'Immediate'),
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # UPDATED: Allow both regular users and job seekers to create alerts
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='job_alerts',
                             limit_choices_to={'user_type__in': ['regular', 'job_seeker']})

    # Alert criteria
    title = models.CharField(max_length=100, help_text="Name this job alert")
    keywords = models.CharField(max_length=200, blank=True, help_text="Keywords to search for")
    location = models.CharField(max_length=100, blank=True, help_text="Location filter")
    remote_only = models.BooleanField(default=False)
    job_type = models.CharField(max_length=20, choices=JobPosting.JOB_TYPE_CHOICES, blank=True)
    experience_level = models.CharField(max_length=20, choices=JobPosting.EXPERIENCE_LEVEL_CHOICES, blank=True)
    industry = models.CharField(max_length=20, choices=JobPosting.INDUSTRY_CHOICES, blank=True)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # Alert settings
    is_active = models.BooleanField(default=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    last_sent = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Job Alert"
        verbose_name_plural = "Job Alerts"

    def __str__(self):
        return f"{self.user.username}'s alert: {self.title}"