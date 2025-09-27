import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage, UserActivity
from django.utils import timezone
from django.db import models  # Add this import if it's missing


User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope["user"]

        print(f"User {self.user} connecting to room {self.room_id}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Set user as online
        await self.set_user_online(True)

        # Send existing messages
        await self.send_existing_messages()

        # Notify others that this user is online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status_update',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_online': True,
                'last_seen': timezone.now().isoformat()
            }
        )

        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to real-time chat with enhanced features'
        }))

        print(f"User {self.user} connected successfully")

    async def disconnect(self, close_code):
        print(f"User {self.user} disconnecting from room {self.room_id}")

        # Set user as offline
        await self.set_user_online(False)

        # Notify others that this user is offline
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status_update',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_online': False,
                'last_seen': timezone.now().isoformat()
            }
        )

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

        print(f"User {self.user} disconnected")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'chat_message':
                message = data['message'].strip()
                if not message:
                    return

                # Save message to database
                saved_message = await self.save_message(message)

                if saved_message:
                    # Get the other user in this chat room
                    other_user_id = await self.get_other_user_id()

                    # Send notification IMMEDIATELY to the recipient
                    if other_user_id:
                        print(f"🚀 Instant notification to user {other_user_id}")
                        await self.send_notification_update(other_user_id)

                    # Then send to all users in room group
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'broadcast_message',
                            'message': message,
                            'sender_id': self.user.id,
                            'sender_name': self.user.username,
                            'timestamp': saved_message['timestamp'],
                            'message_id': saved_message['id'],
                            'delivered': True,
                            'read': False
                        }
                    )
            # ... rest of your existing code

            # In your chat/consumers.py, update the message_read handler:

            elif message_type == 'message_read':

                # Mark message as read

                message_id = data.get('message_id')

                if message_id:
                    await self.mark_message_read(message_id)

                    # Send notification update to the user who read the message

                    await self.send_notification_update(self.user.id)

                    # Notify sender that message was read

                    await self.channel_layer.group_send(

                        self.room_group_name,

                        {

                            'type': 'message_read_update',

                            'message_id': message_id,

                            'read_by_user_id': self.user.id,

                            'read_by_username': self.user.username,

                            'read_at': timezone.now().isoformat()

                        }

                    )

            elif message_type == 'typing_start':
                # User started typing
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'is_typing': True
                    }
                )

            elif message_type == 'typing_stop':
                # User stopped typing
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'typing_indicator',
                        'user_id': self.user.id,
                        'username': self.user.username,
                        'is_typing': False
                    }
                )

        except Exception as e:
            print(f"Error in receive: {e}")

    # Handle broadcasted messages
    async def broadcast_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id'],
            'delivered': event['delivered'],
            'read': event['read'],
            'is_own_message': event['sender_id'] == self.user.id
        }))
        # Remove only these lines:
        # if event['sender_id'] != self.user.id:
        #     print(f"DEBUG: Sending notification update to user {self.user.id}")
        #     await self.send_notification_update(self.user.id)
    # Handle user status updates
    async def user_status_update(self, event):
        # Don't send status updates about yourself
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'user_status',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_online': event['is_online'],
                'last_seen': event['last_seen']
            }))

    # Handle message read updates
    async def message_read_update(self, event):
        # Only send to the message sender
        message_sender_id = await self.get_message_sender(event['message_id'])
        if message_sender_id == self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'message_read',
                'message_id': event['message_id'],
                'read_by_user_id': event['read_by_user_id'],
                'read_by_username': event['read_by_username'],
                'read_at': event['read_at']
            }))

    # Handle typing indicators
    async def typing_indicator(self, event):
        # Don't send typing indicators back to yourself
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing_status',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }))

    @database_sync_to_async
    def save_message(self, message):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            saved_msg = ChatMessage.objects.create(
                room=room,
                sender=self.user,
                message=message,
                delivered=True,
                read=False
            )
            return {
                'id': str(saved_msg.id),
                'timestamp': saved_msg.timestamp.isoformat()
            }
        except Exception as e:
            print(f"Database save error: {e}")
            return None

    @database_sync_to_async
    def mark_message_read(self, message_id):
        try:
            message = ChatMessage.objects.get(id=message_id)
            message.read = True
            message.read_at = timezone.now()  # Add this line
            message.save()
            return True
        except ChatMessage.DoesNotExist:
            return False

    @database_sync_to_async
    def get_message_sender(self, message_id):
        try:
            message = ChatMessage.objects.get(id=message_id)
            return message.sender.id
        except ChatMessage.DoesNotExist:
            return None

    @database_sync_to_async
    def set_user_online(self, is_online):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            activity, created = UserActivity.objects.get_or_create(
                user=self.user,
                defaults={
                    'is_online': is_online,
                    'current_chat_room': room if is_online else None,
                    'last_seen': timezone.now()
                }
            )
            if not created:
                activity.is_online = is_online
                activity.current_chat_room = room if is_online else None
                activity.last_seen = timezone.now()
                activity.save()
        except Exception as e:
            print(f"Error updating user activity: {e}")

    @database_sync_to_async
    def get_existing_messages(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            messages = room.messages.all().order_by('timestamp')
            return [
                {
                    'id': str(msg.id),
                    'message': msg.message,
                    'sender_id': msg.sender.id,
                    'sender_name': msg.sender.username,
                    'timestamp': msg.timestamp.isoformat(),
                    'delivered': getattr(msg, 'delivered', True),
                    'read': getattr(msg, 'read', False)
                }
                for msg in messages
            ]
        except Exception as e:
            print(f"Error loading messages: {e}")
            return []

    @database_sync_to_async
    def get_other_user_status(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)

            # Handle both chat types
            if room.investor and room.regular_user:
                other_user = room.investor if self.user == room.regular_user else room.regular_user
            elif room.participant_1 and room.participant_2:
                other_user = room.participant_2 if self.user == room.participant_1 else room.participant_1
            else:
                return None

            try:
                activity = UserActivity.objects.get(user=other_user)
                return {
                    'user_id': other_user.id,
                    'username': other_user.username,
                    'is_online': activity.is_online,
                    'last_seen': activity.last_seen.isoformat()
                }
            except UserActivity.DoesNotExist:
                return {
                    'user_id': other_user.id,
                    'username': other_user.username,
                    'is_online': False,
                    'last_seen': None
                }
        except Exception as e:
            print(f"Error getting user status: {e}")
            return None

    async def send_existing_messages(self):
        # Send chat history
        messages = await self.get_existing_messages()

        for msg in messages:
            await self.send(text_data=json.dumps({
                'type': 'existing_message',
                'message': msg['message'],
                'sender_id': msg['sender_id'],
                'sender_name': msg['sender_name'],
                'timestamp': msg['timestamp'],
                'message_id': msg['id'],
                'delivered': msg['delivered'],
                'read': msg['read'],
                'is_own_message': msg['sender_id'] == self.user.id
            }))

        # Send other user's online status
        other_user_status = await self.get_other_user_status()
        if other_user_status:
            await self.send(text_data=json.dumps({
                'type': 'user_status',
                'user_id': other_user_status['user_id'],
                'username': other_user_status['username'],
                'is_online': other_user_status['is_online'],
                'last_seen': other_user_status['last_seen']
            }))

        print(f"Sent {len(messages)} messages and user status to {self.user}")

    # Add this method to your existing ChatConsumer class
    async def send_notification_update(self, recipient_user_id):
        """Send notification update to specific user"""
        # Get recipient's unread count
        unread_count = await self.get_user_unread_count(recipient_user_id)

        # Send to recipient's notification group
        await self.channel_layer.group_send(
            f'notifications_{recipient_user_id}',
            {
                'type': 'notification_update',
                'unread_count': unread_count
            }
        )

    @database_sync_to_async
    def get_user_unread_count(self, user_id):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Include ALL chat types - traditional AND admin chats
            user_chat_rooms = ChatRoom.objects.filter(
                models.Q(investor=user) |
                models.Q(regular_user=user) |
                models.Q(participant_1=user) |
                models.Q(participant_2=user)
            )

            unread_count = ChatMessage.objects.filter(
                room__in=user_chat_rooms,
                read=False
            ).exclude(sender=user).count()

            return unread_count
        except Exception as e:
            print(f"Error getting user unread count: {e}")
            return 0

    @database_sync_to_async
    def get_other_user_id(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)

            # Handle both traditional and admin chat types
            if room.investor and room.regular_user:
                # Traditional investor-entrepreneur chat
                other_user = room.investor if self.user == room.regular_user else room.regular_user
            elif room.participant_1 and room.participant_2:
                # Admin or flexible participant chat
                other_user = room.participant_2 if self.user == room.participant_1 else room.participant_1
            else:
                return None

            return other_user.id
        except Exception as e:
            print(f"Error getting other user: {e}")
            return None


# ADD THIS NEW CLASS TO YOUR CONSUMERS.PY FILE:
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_authenticated:
            self.user_group_name = f'notifications_{self.scope["user"].id}'
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
            print(f"🔔 User {self.scope['user'].username} connected to notifications")
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
            print(f"🔔 User {self.scope['user'].username} disconnected from notifications")

    async def notification_update(self, event):
        """Send notification update to client"""
        await self.send(text_data=json.dumps({
            'type': 'unread_count_update',
            'unread_count': event['unread_count']
        }))
        print(f"🔔 Sent notification update: {event['unread_count']} to {self.scope['user'].username}")