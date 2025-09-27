import uuid
from django.db import models
from django.conf import settings


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

    # Remove unique_together since we now have multiple field combinations
    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        # Handle different chat types
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


# Keep your existing ChatMessage and UserActivity models unchanged
class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender.username}: {self.message[:50]}..."


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