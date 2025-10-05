import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
import os


# Validation functions
def validate_file_size(file):
    """Validate file size"""
    max_size = 20 * 1024 * 1024  # 20MB
    if file.size > max_size:
        raise ValidationError('File size cannot exceed 20MB')


def validate_file_extension(filename):
    """Validate file extension"""
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt']
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'File extension {ext} is not allowed')


def validate_file_content(file):
    """Validate actual file content using magic numbers (requires python-magic)"""
    allowed_mime_types = [
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf', 'text/plain'
    ]

    try:
        import magic
        # Read first 1KB to determine file type
        file_start = file.read(1024)
        file.seek(0)  # Reset file pointer

        # Get MIME type from actual content
        file_mime = magic.from_buffer(file_start, mime=True)

        if file_mime not in allowed_mime_types:
            raise ValidationError(f'File content type {file_mime} is not allowed')
    except ImportError:
        # python-magic not installed, skip content validation
        pass
    except Exception as e:
        raise ValidationError(f'Could not validate file: {str(e)}')


def chat_file_upload_path(instance, filename):
    """Generate upload path for chat files"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('chat_files', str(instance.room.id), filename)


class ChatRoom(models.Model):
    """Represents a conversation between users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Keep existing fields for backward compatibility
    investor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='investor_rooms', null=True, blank=True)
    regular_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name='regular_user_rooms', null=True, blank=True)

    # Add flexible participant fields for admin chats
    participant_1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name='chat_participant_1', null=True, blank=True)
    participant_2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                      related_name='chat_participant_2', null=True, blank=True)

    related_pitch = models.ForeignKey('pitches.IdeaPitch', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        if self.investor and self.regular_user:
            return f"Chat: {self.investor.username} - {self.regular_user.username}"
        elif self.participant_1 and self.participant_2:
            return f"Chat: {self.participant_1.username} - {self.participant_2.username}"
        return f"Chat Room {self.id}"

    @property
    def room_name(self):
        if self.investor and self.regular_user:
            return f"chat_{self.investor.id}_{self.regular_user.id}"
        elif self.participant_1 and self.participant_2:
            return f"chat_{self.participant_1.id}_{self.participant_2.id}"
        return f"chat_{self.id}"

    def get_other_participant(self, user):
        """Get the other participant in the chat"""
        if self.investor and self.regular_user:
            return self.regular_user if user == self.investor else self.investor
        elif self.participant_1 and self.participant_2:
            return self.participant_2 if user == self.participant_1 else self.participant_1
        return None

    def get_participants(self):
        """Get both participants"""
        if self.investor and self.regular_user:
            return [self.investor, self.regular_user]
        elif self.participant_1 and self.participant_2:
            return [self.participant_1, self.participant_2]
        return []

    def get_latest_message(self):
        """Get the most recent message in this chat room"""
        return self.messages.first()

    def get_unread_count(self, user):
        """Get count of unread messages for a specific user"""
        return self.messages.filter(is_read=False).exclude(sender=user).count()

    def mark_messages_read(self, user):
        """Mark all messages as read for a specific user"""
        self.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)


class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    # File upload fields
    file = models.FileField(upload_to=chat_file_upload_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(default=0)
    file_type = models.CharField(max_length=100, blank=True)

    # Delivery tracking
    delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        if self.message:
            return f"{self.sender.username}: {self.message[:50]}..."
        elif self.file:
            return f"{self.sender.username}: [File: {self.file_name}]"
        return f"{self.sender.username}: [Empty message]"

    def get_file_icon(self):
        """Return appropriate FontAwesome icon based on file type"""
        if not self.file_type:
            return 'file'

        if 'image' in self.file_type:
            return 'file-image'
        elif 'pdf' in self.file_type:
            return 'file-pdf'
        elif 'text' in self.file_type:
            return 'file-alt'
        else:
            return 'file'

    def format_file_size(self):
        """Format file size in human readable format"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


class UserActivity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activity')
    last_seen = models.DateTimeField(auto_now=True)
    is_online = models.BooleanField(default=False)
    current_chat_room = models.ForeignKey(ChatRoom, on_delete=models.SET_NULL, null=True, blank=True)
    is_typing = models.BooleanField(default=False)
    typing_in_room = models.ForeignKey(ChatRoom, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='typing_users')

    def __str__(self):
        return f"{self.user.username} - {'Online' if self.is_online else 'Offline'}"


class SupportTicket(models.Model):
    """Support tickets for user-admin communication"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    CATEGORY_CHOICES = [
        ('technical', 'Technical Issue'),
        ('payment', 'Payment/Billing'),
        ('account', 'Account Problem'),
        ('job', 'Job Posting'),
        ('funding', 'Funding Question'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    chat_room = models.OneToOneField(ChatRoom, on_delete=models.CASCADE, related_name='support_ticket', null=True)

    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_support_tickets'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Ticket #{self.id} - {self.subject}"

    def get_message_count(self):
        """Get total number of messages in this ticket"""
        if self.chat_room:
            return self.chat_room.messages.count()
        return 0