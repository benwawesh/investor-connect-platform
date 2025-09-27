# pitches/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import IdeaPitch, PitchCategory, PitchInterest, PitchFile, InvestorPost
from .forms import PitchForm, InvestorPostForm


@login_required
def create_pitch(request):
    """Create a new pitch with optional file uploads"""
    if not request.user.can_access_platform:
        messages.error(request, "Please verify your account first.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = PitchForm(request.POST)

        if form.is_valid():
            pitch = form.save(commit=False)
            pitch.user = request.user
            pitch.save()

            # Handle file uploads
            files = request.FILES.getlist('files')
            file_types = request.POST.getlist('file_types')
            descriptions = request.POST.getlist('descriptions')
            # Remove this line: is_public_list = request.POST.getlist('is_public')

            files_uploaded = 0
            for i, file in enumerate(files):
                if file:
                    PitchFile.objects.create(
                        pitch=pitch,
                        file=file,
                        file_type=file_types[i] if i < len(file_types) else 'other',
                        description=descriptions[i] if i < len(descriptions) else '',
                        # Remove this line: is_public=str(i) in is_public_list,
                    )
                    files_uploaded += 1

            if files_uploaded > 0:
                messages.success(request, f'Pitch submitted successfully with {files_uploaded} file(s)!')
            else:
                messages.success(request, 'Pitch submitted successfully!')
            return redirect('accounts:dashboard')
    else:
        form = PitchForm()

    return render(request, 'pitches/create_pitch.html', {'form': form})


# In pitches/views.py - update the pitch_detail function:

# Add this to your pitches/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import IdeaPitch, PitchInterest
from chat.models import ChatRoom


@login_required
def pitch_detail(request, pitch_id):
    """Display detailed view of a pitch"""
    pitch = get_object_or_404(IdeaPitch, id=pitch_id)

    # Check if current user has expressed interest
    user_has_interest = False
    if request.user.user_type == 'investor':
        user_has_interest = PitchInterest.objects.filter(
            pitch=pitch,
            investor=request.user
        ).exists()

    # Check if user can view files (interested investors, pitch owner, or admin)
    user_can_view_files = (
            request.user == pitch.user or  # Pitch owner
            request.user.is_staff or  # Admin
            (request.user.user_type == 'investor' and user_has_interest)  # Interested investor
    )

    # Get chat room if user is investor and has expressed interest
    chat_room = None
    unread_count = 0
    if request.user.user_type == 'investor' and user_has_interest:
        try:
            chat_room = ChatRoom.objects.get(
                investor=request.user,
                regular_user=pitch.user,
                related_pitch=pitch
            )
            # Get unread message count for this investor
            unread_count = chat_room.messages.filter(
                sender=pitch.user,  # Messages from pitch owner
                is_read=False
            ).count()
        except ChatRoom.DoesNotExist:
            # Chat room should exist if user has interest, but handle gracefully
            pass

    # Get user's chat rooms if they're the pitch owner (for the interested investors section)
    user_chat_rooms = []
    if request.user == pitch.user:
        user_chat_rooms = ChatRoom.objects.filter(
            regular_user=request.user,
            related_pitch=pitch
        )

    context = {
        'pitch': pitch,
        'user_has_interest': user_has_interest,
        'user_can_view_files': user_can_view_files,
        'chat_room': chat_room,
        'unread_count': unread_count,
        'user_chat_rooms': user_chat_rooms,
    }

    return render(request, 'pitches/pitch_detail.html', context)

@login_required
def debug_user_pitches(request):
    """Debug view to see user's pitches"""
    user_pitches = IdeaPitch.objects.filter(user=request.user)
    all_pitches = IdeaPitch.objects.all()

    context = {
        'user_pitches': user_pitches,
        'user_pitches_count': user_pitches.count(),
        'all_pitches': all_pitches,
        'current_user': request.user,
    }
    return render(request, 'pitches/debug.html', context)


@login_required
def pitch_list(request):
    """List user's own pitches"""
    if not request.user.can_access_platform:
        messages.error(request, "Please verify your account first.")
        return redirect('accounts:dashboard')

    # Get user's pitches
    pitches = request.user.pitches.all().order_by('-submitted_at')

    return render(request, 'pitches/pitch_list.html', {'pitches': pitches})



@login_required
def investor_pitch_list(request):
    """Allow investors to browse approved pitches"""
    if request.user.user_type != 'investor':
        messages.error(request, "Only investors can access this page.")
        return redirect('accounts:dashboard')

    # Get all approved pitches
    approved_pitches = IdeaPitch.objects.filter(status='approved').order_by('-submitted_at')

    context = {
        'pitches': approved_pitches,
        'total_count': approved_pitches.count(),
    }
    return render(request, 'pitches/investor_pitch_list.html', context)


@login_required
def add_interest(request, pitch_id):
    """Allow investors to express interest in a pitch"""
    if request.user.user_type != 'investor':
        messages.error(request, "Only investors can express interest in pitches.")
        return redirect('accounts:dashboard')

    pitch = get_object_or_404(IdeaPitch, id=pitch_id)

    if pitch.status != 'approved':
        messages.error(request, "You can only express interest in approved pitches.")
        return redirect('pitches:pitch_detail', pitch_id=pitch_id)

    # Check if interest already exists
    interest, created = PitchInterest.objects.get_or_create(
        pitch=pitch,
        investor=request.user
    )

    if created:
        # Create chat room when interest is first expressed
        from chat.models import ChatRoom
        chat_room, room_created = ChatRoom.objects.get_or_create(
            investor=request.user,
            regular_user=pitch.user,
            defaults={'related_pitch': pitch}
        )
        if room_created:
            messages.success(request, f"You've successfully expressed interest in '{pitch.title}'! A chat room has been created.")
        else:
            messages.success(request, f"You've successfully expressed interest in '{pitch.title}'! You can now chat.")
    else:
        messages.info(request, "You've already expressed interest in this pitch.")

    return redirect('pitches:pitch_detail', pitch_id=pitch_id)


@login_required
def remove_interest(request, pitch_id):
    """Allow investors to remove their interest in a pitch"""
    if request.user.user_type != 'investor':
        messages.error(request, "Only investors can manage pitch interests.")
        return redirect('accounts:dashboard')

    pitch = get_object_or_404(IdeaPitch, id=pitch_id)

    try:
        interest = PitchInterest.objects.get(
            pitch=pitch,
            investor=request.user
        )
        interest.delete()
        messages.success(request, f"You've removed your interest in '{pitch.title}'.")
    except PitchInterest.DoesNotExist:
        messages.error(request, "You haven't expressed interest in this pitch.")

    return redirect('pitches:pitch_detail', pitch_id=pitch_id)



@login_required
def remove_interest(request, pitch_id):
    """Allow investors to remove their interest in a pitch"""
    if request.user.user_type != 'investor':
        messages.error(request, "Only investors can manage pitch interests.")
        return redirect('accounts:dashboard')

    pitch = get_object_or_404(IdeaPitch, id=pitch_id)

    try:
        interest = PitchInterest.objects.get(
            pitch=pitch,
            investor=request.user
        )
        interest.delete()
        messages.success(request, f"You've removed your interest in '{pitch.title}'.")
    except PitchInterest.DoesNotExist:
        messages.error(request, "You haven't expressed interest in this pitch.")

    return redirect('pitches:pitch_detail', pitch_id=pitch_id)


@login_required
def investor_posts_feed(request):
    """Display all investor posts for verified users"""
    if not request.user.is_staff and not request.user.is_verified:
        messages.error(request, "Please verify your account to view investor posts.")
        return redirect('accounts:dashboard')

    # Get all public posts, featured first - with profile data
    posts = InvestorPost.objects.filter(is_public=True).select_related(
        'investor',
        'investor__userprofileextension'
    ).order_by('-is_featured', '-created_at')

    # Filter by post type if requested
    post_type = request.GET.get('type')
    if post_type:
        posts = posts.filter(post_type=post_type)

    # Filter by tags if requested
    tag = request.GET.get('tag')
    if tag:
        posts = posts.filter(tags__icontains=tag)

    # Ensure all investors have profile extensions
    from accounts.models import UserProfileExtension
    for post in posts:
        if not hasattr(post.investor, 'userprofileextension'):
            UserProfileExtension.objects.get_or_create(user=post.investor)

    context = {
        'posts': posts,
        'current_filter': post_type,
        'current_tag': tag,
        'post_types': InvestorPost.POST_TYPE_CHOICES,
    }

    return render(request, 'pitches/investor_posts_feed.html', context)

@login_required
def create_investor_post(request):
    """Allow investors and admin staff to create new posts"""
    # CHANGE THIS LINE - allow both investors and admin staff
    if request.user.user_type != 'investor' and not request.user.is_staff:
        messages.error(request, "Only investors and admin staff can create posts.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = InvestorPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.investor = request.user
            post.save()
            messages.success(request, 'Post created successfully!')
            return redirect('pitches:investor_posts_feed')
    else:
        form = InvestorPostForm()

    return render(request, 'pitches/create_investor_post.html', {'form': form})


@login_required
def investor_post_detail(request, post_id):
    """Display individual investor post"""
    post = get_object_or_404(InvestorPost, id=post_id)

    if not post.is_public and request.user != post.investor and not request.user.is_staff:
        messages.error(request, "This post is not available.")
        return redirect('pitches:investor_posts_feed')

    # Increment read count
    post.increment_read_count()

    return render(request, 'pitches/investor_post_detail.html', {'post': post})

@login_required
def pitch_guidelines(request):
    context = {
        'title': 'Pitch Guidelines'
    }
    return render(request, 'pitches/pitch_guidelines.html', context)