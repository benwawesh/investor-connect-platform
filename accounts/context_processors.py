# In accounts/context_processors.py
from django.db import models
from chat.models import ChatMessage, ChatRoom


def unread_messages(request):
    """Add unread message count to all templates, excluding current chat room"""
    if request.user.is_authenticated:
        try:
            # Get all chat rooms for this user - including admin chats
            user_chat_rooms = ChatRoom.objects.filter(
                models.Q(investor=request.user) |
                models.Q(regular_user=request.user) |
                models.Q(participant_1=request.user) |
                models.Q(participant_2=request.user)
            )

            # Check if user is currently in a specific chat room
            current_room_id = None
            if '/chat/' in request.path and request.path != '/chat/' and not request.path.endswith('/chat/'):
                # Extract room ID from URL path like /chat/room-id/
                path_parts = request.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    current_room_id = path_parts[1]

            # Count unread messages, excluding current room if user is in one
            unread_query = ChatMessage.objects.filter(
                room__in=user_chat_rooms,
                read=False
            ).exclude(sender=request.user)

            # If user is in a chat room, exclude messages from that room
            if current_room_id:
                unread_query = unread_query.exclude(room__id=current_room_id)

            unread_count = unread_query.count()

            return {'unread_message_count': unread_count}
        except Exception as e:
            print(f"Error in unread_messages context processor: {e}")
            return {'unread_message_count': 0}

    return {'unread_message_count': 0}