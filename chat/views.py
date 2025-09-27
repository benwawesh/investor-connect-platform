# chat/views.py - Updated with admin support

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage, UserActivity
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import models

User = get_user_model()


@login_required
def chat_list(request):
    """Display list of user's chat rooms - updated for admin support"""

    # Get ALL chat rooms where current user participates
    chat_rooms = ChatRoom.objects.filter(
        Q(investor=request.user) | Q(regular_user=request.user) |
        Q(participant_1=request.user) | Q(participant_2=request.user)
    ).order_by('-created_at')

    # Build chat data with message history
    chat_data = []
    for room in chat_rooms:
        # Determine who the other user is - handle both old and new chat types
        other_user = None
        other_user_type = ""

        if room.investor and room.regular_user:
            # Traditional investor-entrepreneur chat
            if request.user == room.investor:
                other_user = room.regular_user
                other_user_type = "Entrepreneur"
                unread_count = room.messages.filter(sender=room.regular_user, is_read=False).count()
            else:
                other_user = room.investor
                other_user_type = "Investor"
                unread_count = room.messages.filter(sender=room.investor, is_read=False).count()
        elif room.participant_1 and room.participant_2:
            # Admin or flexible participant chat
            if request.user == room.participant_1:
                other_user = room.participant_2
            else:
                other_user = room.participant_1

            # Determine user type
            if other_user.is_staff:
                other_user_type = "Administrator"
            elif other_user.is_investor:
                other_user_type = "Investor"
            else:
                other_user_type = "Entrepreneur"

            unread_count = room.messages.filter(sender=other_user, is_read=False).count()

        if other_user:
            # Get the last message in this conversation
            last_message = room.messages.order_by('-timestamp').first()
            total_messages = room.messages.count()

            chat_data.append({
                'room': room,
                'other_user': other_user,
                'other_user_type': other_user_type,
                'unread_count': unread_count,
                'last_message': last_message,
                'total_messages': total_messages,
                'last_activity': last_message.timestamp if last_message else room.created_at,
            })

    # Sort by most recent activity
    chat_data.sort(key=lambda x: x['last_activity'], reverse=True)

    return render(request, 'chat/chat_list.html', {
        'chat_data': chat_data,
        'total_chats': len(chat_data)
    })


@login_required
def chat_room(request, room_id):
    """Display chat room - updated for admin support"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)

    # Check permissions and get other user - handle both chat types
    has_access = False
    other_user = None

    if chat_room.investor and chat_room.regular_user:
        has_access = request.user in [chat_room.regular_user, chat_room.investor]
        other_user = chat_room.regular_user if request.user == chat_room.investor else chat_room.investor
    elif chat_room.participant_1 and chat_room.participant_2:
        has_access = request.user in [chat_room.participant_1, chat_room.participant_2]
        other_user = chat_room.participant_2 if request.user == chat_room.participant_1 else chat_room.participant_1

    if not has_access:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Access denied'})
        messages.error(request, "You don't have access to this chat.")
        return redirect('chat:chat_list')

    # Handle AJAX requests for getting messages
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('get_messages'):
        try:
            # Get all messages for this chat room
            all_messages = ChatMessage.objects.filter(room=chat_room).order_by('timestamp')

            # Get other user info for status
            other_user_id = request.GET.get('other_user_id')
            is_online = False
            is_typing = False
            last_seen = None

            if other_user_id:
                try:
                    other_user_obj = User.objects.get(id=other_user_id)

                    try:
                        other_activity = UserActivity.objects.get(user=other_user_obj)

                        # Check if user is online (must be marked online AND active within last 1 minute)
                        time_diff = timezone.now() - other_activity.last_seen
                        is_recently_active = time_diff.total_seconds() < 60  # 1 minute
                        is_online = other_activity.is_online and is_recently_active

                        is_typing = other_activity.is_typing and other_activity.typing_in_room == chat_room and is_online
                        last_seen = other_activity.last_seen

                    except UserActivity.DoesNotExist:
                        UserActivity.objects.create(
                            user=other_user_obj,
                            is_online=False
                        )
                        is_online = False
                        is_typing = False
                        last_seen = timezone.now()

                except User.DoesNotExist:
                    pass

            # Mark messages from other user as delivered and read
            if other_user_id:
                try:
                    other_user_obj = User.objects.get(id=other_user_id)

                    # Mark as delivered
                    undelivered_messages = ChatMessage.objects.filter(
                        room=chat_room,
                        sender=other_user_obj,
                        delivered=False
                    )
                    undelivered_messages.update(delivered=True, delivered_at=timezone.now())

                    # Mark as read
                    unread_messages = ChatMessage.objects.filter(
                        room=chat_room,
                        sender=other_user_obj,
                        read=False
                    )
                    unread_messages.update(read=True, read_at=timezone.now())

                except User.DoesNotExist:
                    pass

            # Prepare messages data
            messages_data = []
            for message in all_messages:
                delivered = getattr(message, 'delivered', True)
                read = getattr(message, 'read', True)

                messages_data.append({
                    'id': str(message.id),
                    'message': message.message,
                    'timestamp': message.timestamp.isoformat(),
                    'sender_id': message.sender.id,
                    'sender_name': message.sender.username,
                    'delivered': delivered,
                    'read': read,
                })

            return JsonResponse({
                'success': True,
                'messages': messages_data,
                'other_user_online': is_online,
                'other_user_last_seen': last_seen.isoformat() if last_seen else timezone.now().isoformat(),
                'other_user_typing': is_typing,
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return render(request, 'chat/chat_room.html', {
        'chat_room': chat_room,
        'other_user': other_user,  # This is the key addition
        'messages': [],
    })

@login_required
def start_chat_with_user(request, username):
    """Start a chat with any user - supports admin chats"""
    other_user = get_object_or_404(User, username=username)

    if request.user == other_user:
        messages.error(request, "You cannot chat with yourself.")
        return redirect('chat:chat_list')

    # Check if chat already exists
    chat_room = None

    # First check traditional investor-entrepreneur chats
    if request.user.is_investor and not other_user.is_investor and not other_user.is_staff:
        chat_room, created = ChatRoom.objects.get_or_create(
            investor=request.user,
            regular_user=other_user
        )
    elif other_user.is_investor and not request.user.is_investor and not request.user.is_staff:
        chat_room, created = ChatRoom.objects.get_or_create(
            investor=other_user,
            regular_user=request.user
        )
    else:
        # Admin chat or non-traditional pairing - use participant fields
        chat_room = ChatRoom.objects.filter(
            Q(participant_1=request.user, participant_2=other_user) |
            Q(participant_1=other_user, participant_2=request.user)
        ).first()

        if not chat_room:
            chat_room = ChatRoom.objects.create(
                participant_1=request.user,
                participant_2=other_user
            )

    return redirect('chat:chat_room', room_id=chat_room.id)


# Keep your existing send_message, test_chat_room, update_activity, and typing_status views unchanged
@login_required
def send_message(request, room_id):
    """Send a message via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    chat_room = get_object_or_404(ChatRoom, id=room_id)

    # Check permissions - handle both chat types
    has_access = False
    if chat_room.investor and chat_room.regular_user:
        has_access = request.user in [chat_room.regular_user, chat_room.investor]
    elif chat_room.participant_1 and chat_room.participant_2:
        has_access = request.user in [chat_room.participant_1, chat_room.participant_2]

    if not has_access:
        return JsonResponse({'success': False, 'error': 'Access denied'})

    message_text = request.POST.get('message', '').strip()
    if not message_text:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty'})

    # Create message
    message = ChatMessage.objects.create(
        room=chat_room,
        sender=request.user,
        message=message_text
    )

    return JsonResponse({
        'success': True,
        'message': {
            'id': str(message.id),
            'text': message.message,
            'created_at': message.timestamp.strftime('%H:%M'),
            'sender_id': message.sender.id
        }
    })


@login_required
def update_activity(request):
    """Update user's last activity for online status"""
    if request.method == 'POST':
        # Check if user is going offline
        if request.POST.get('offline') == 'true':
            try:
                activity = UserActivity.objects.get(user=request.user)
                activity.is_online = False
                activity.is_typing = False
                activity.save()
            except UserActivity.DoesNotExist:
                pass
            return JsonResponse({'success': True})

        # Normal activity update - user is active
        room_id = request.POST.get('room_id')
        chat_room = get_object_or_404(ChatRoom, id=room_id) if room_id else None

        activity, created = UserActivity.objects.get_or_create(
            user=request.user,
            defaults={
                'is_online': True,
                'current_chat_room': chat_room
            }
        )

        if not created:
            activity.is_online = True
            activity.current_chat_room = chat_room
            activity.save()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False})


@login_required
def typing_status(request, room_id):
    """Update user's typing status"""
    if request.method == 'POST':
        chat_room = get_object_or_404(ChatRoom, id=room_id)
        is_typing = request.POST.get('is_typing') == 'true'

        # Update user activity
        activity, created = UserActivity.objects.get_or_create(
            user=request.user,
            defaults={
                'is_typing': is_typing,
                'typing_in_room': chat_room if is_typing else None
            }
        )

        if not created:
            activity.is_typing = is_typing
            activity.typing_in_room = chat_room if is_typing else None
            activity.save()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False})


@login_required
def test_chat_room(request, room_id):
    """Minimal test view"""
    chat_room = get_object_or_404(ChatRoom, id=room_id)
    return render(request, 'chat/test_chat.html', {
        'chat_room': chat_room,
    })