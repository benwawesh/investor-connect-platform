import uuid
import os
from django.db import models
from django.conf import settings  # Change this import
from django.core.validators import FileExtensionValidator

# Remove this line:
# User = get_user_model()

# Replace all User references with settings.AUTH_USER_MODEL


class PitchCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Pitch Categories"

    def __str__(self):
        return self.name


class IdeaPitch(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pitches')  # Changed
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(PitchCategory, on_delete=models.SET_NULL, null=True, blank=True)
    budget_required = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    timeline = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,  # Changed
                                    related_name='reviewed_pitches')
    admin_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class InvestorPost(models.Model):
    POST_TYPE_CHOICES = [
        ('testimonial', 'Testimonial'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')  # Changed
    title = models.CharField(max_length=200)
    content = models.TextField()
    post_type = models.CharField(max_length=25, choices=POST_TYPE_CHOICES, default='testimonial')

    # Keep your existing fields:
    featured_image = models.ImageField(upload_to='investor_posts/%Y/%m/', null=True, blank=True)
    tags = models.CharField(max_length=200, blank=True, help_text='Comma-separated tags')
    read_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False, help_text='Featured posts appear at top')
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return f"{self.title} - {self.investor.username}"

    def get_tags_list(self):
        """Return tags as a list"""
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    def increment_read_count(self):
        """Increment the read count"""
        self.read_count += 1
        self.save(update_fields=['read_count'])


class PitchInterest(models.Model):
    """Track which investors are interested in which pitches"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pitch_interests')  # Changed
    pitch = models.ForeignKey(IdeaPitch, on_delete=models.CASCADE, related_name='interested_investors')
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('investor', 'pitch')

    def __str__(self):
        return f"{self.investor.username} interested in {self.pitch.title}"


def pitch_file_upload_path(instance, filename):
    """Generate upload path for pitch files"""
    # Get file extension
    ext = filename.split('.')[-1]
    # Create new filename with UUID
    filename = f"{uuid.uuid4()}.{ext}"
    # Return upload path
    return f"pitch_files/{instance.pitch.id}/{filename}"


class PitchFile(models.Model):
    # ... rest of your PitchFile model stays the same
    FILE_TYPE_CHOICES = [
        ('business_plan', 'Business Plan'),
        ('financial', 'Financial Documents'),
        ('image', 'Images/Screenshots'),
        ('prototype', 'Prototype Files'),
        ('presentation', 'Presentation'),
        ('other', 'Other Documents'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pitch = models.ForeignKey(IdeaPitch, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(
        upload_to=pitch_file_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'ppt', 'pptx', 'xls', 'xlsx']
            )
        ]
    )
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    original_filename = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField()  # in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} - {self.pitch.title}"

    def get_file_size_display(self):
        """Return human readable file size"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def get_file_icon(self):
        """Return icon class based on file type"""
        icons = {
            'pdf': 'fas fa-file-pdf text-red-500',
            'doc': 'fas fa-file-word text-blue-500',
            'docx': 'fas fa-file-word text-blue-500',
            'jpg': 'fas fa-file-image text-green-500',
            'jpeg': 'fas fa-file-image text-green-500',
            'png': 'fas fa-file-image text-green-500',
            'ppt': 'fas fa-file-powerpoint text-orange-500',
            'pptx': 'fas fa-file-powerpoint text-orange-500',
            'xls': 'fas fa-file-excel text-green-600',
            'xlsx': 'fas fa-file-excel text-green-600',
        }
        ext = self.file.name.split('.')[-1].lower()
        return icons.get(ext, 'fas fa-file text-gray-500')

    def save(self, *args, **kwargs):
        # Store original filename and file size
        if self.file:
            self.original_filename = self.file.name
            self.file_size = self.file.size
        super().save(*args, **kwargs)