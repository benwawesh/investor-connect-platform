import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatMessage, ChatRoom
from django.db import models

User = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if self.user.is_authenticated:
            # Join user-specific notification group
            self.notification_group_name = f'notifications_{self.user.id}'

            await self.channel_layer.group_add(
                self.notification_group_name,
                self.channel_name
            )

            await self.accept()

            # Send current unread count
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'unread_count_update',
                'unread_count': unread_count
            }))

            print(f"🔔 Notification WebSocket connected for {self.user.username} with {unread_count} unread")
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group_name'):
            await self.channel_layer.group_discard(
                self.notification_group_name,
                self.channel_name
            )
        print(f"🔔 Notification WebSocket disconnected for {self.user.username}")

    # In chat/notification_consumer.py - update the notification_update method
    async def notification_update(self, event):
        # Get current room from user's session or connection info if available
        unread_count = event['unread_count']

        await self.send(text_data=json.dumps({
            'type': 'unread_count_update',
            'unread_count': unread_count,
            'exclude_current_room': True  # Flag to indicate this excludes current room
        }))
        print(f"🔔 Sent notification update: {unread_count} unread to {self.user.username}")

    @database_sync_to_async
    def get_unread_count(self):
        try:
            user_chat_rooms = ChatRoom.objects.filter(
                models.Q(investor=self.user) | models.Q(regular_user=self.user)
            )

            unread_count = ChatMessage.objects.filter(
                room__in=user_chat_rooms,
                read=False
            ).exclude(sender=self.user).count()

            return unread_count
        except Exception as e:
            print(f"Error getting unread count: {e}")
            return 0