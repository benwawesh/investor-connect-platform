from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json
import csv

from accounts.models import CustomUser
from pitches.models import IdeaPitch, PitchCategory
from payments.models import SubscriptionPayment
from jobs.models import JobPosting, JobApplication, JobAlert, JobSavedJob
from .forms import CategoryForm, InvestorRegistrationForm, PitchReviewForm


def admin_required(view_func):
    """Custom decorator to check if user is admin/staff"""

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('accounts:dashboard')
        return view_func(request, *args, **kwargs)

    return wrapper


@admin_required
def admin_dashboard(request):
    """Enhanced admin dashboard with comprehensive job management integration"""
    # Get statistics
    pending_pitches = IdeaPitch.objects.filter(status='pending').count()
    pending_users = CustomUser.objects.filter(
        user_type='regular',
        subscription_paid=True,
        is_verified=False
    ).count()
    total_users = CustomUser.objects.count()
    total_categories = PitchCategory.objects.count()

    # ADD MISSING VARIABLES:
    total_investors = CustomUser.objects.filter(user_type='investor').count()
    total_entrepreneurs = CustomUser.objects.filter(user_type='regular').count()

    # Enhanced job-related statistics
    total_jobs = JobPosting.objects.count()
    active_jobs = JobPosting.objects.filter(is_active=True).count()
    total_applications = JobApplication.objects.count()
    pending_applications = JobApplication.objects.filter(status='pending').count()
    job_seekers = CustomUser.objects.filter(user_type='job_seeker').count()

    # Recent activity
    recent_pitches = IdeaPitch.objects.filter(status='pending').order_by('-submitted_at')[:5]
    recent_payments = SubscriptionPayment.objects.filter(status='completed').order_by('-payment_date')[:5]
    recent_users = CustomUser.objects.filter(user_type='regular').order_by('-created_at')[:5]

    # FIXED: Enhanced recent job activity
    recent_jobs = JobPosting.objects.filter(is_active=True).order_by('-created_at')[:5]
    recent_applications = JobApplication.objects.select_related('applicant', 'job_posting').order_by('-applied_at')[:5]

    context = {
        'pending_pitches': pending_pitches,
        'pending_users': pending_users,
        'total_users': total_users,
        'total_categories': total_categories,
        'recent_pitches': recent_pitches,
        'recent_payments': recent_payments,
        'recent_users': recent_users,

        # MISSING CONTEXT VARIABLES:
        'total_investors': total_investors,
        'total_entrepreneurs': total_entrepreneurs,

        # Job statistics
        'total_jobs': total_jobs,
        'active_jobs': active_jobs,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'job_seekers': job_seekers,
        'recent_jobs': recent_jobs,
        'recent_applications': recent_applications,
    }
    return render(request, 'admin_panel/dashboard.html', context)

@admin_required
def manage_categories(request):
    categories = PitchCategory.objects.all().order_by('name')

    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('admin_panel:manage_categories')
    else:
        form = CategoryForm()

    context = {
        'categories': categories,
        'form': form,
    }
    return render(request, 'admin_panel/manage_categories.html', context)


@admin_required
@require_POST
def delete_category(request, category_id):
    category = get_object_or_404(PitchCategory, id=category_id)
    category_name = category.name
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    return redirect('admin_panel:manage_categories')


@admin_required
def user_management(request):
    """Enhanced user management with filters and search"""
    users = CustomUser.objects.select_related('userprofileextension').all()

    # Filter options
    user_type = request.GET.get('user_type')
    verification_status = request.GET.get('verification_status')
    account_status = request.GET.get('account_status')
    search_query = request.GET.get('search')

    if user_type:
        users = users.filter(user_type=user_type)

    if verification_status == 'verified':
        users = users.filter(is_verified=True)
    elif verification_status == 'pending':
        users = users.filter(is_verified=False)

    if account_status:
        users = users.filter(account_status=account_status)

    if search_query:
        # FIXED: Search across correct fields including phone_number
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query) |  # Added phone number search
            Q(userprofileextension__first_name__icontains=search_query) |  # Fixed: reference through relationship
            Q(userprofileextension__last_name__icontains=search_query)     # Fixed: reference through relationship
        )

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(users.order_by('-created_at'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'user_types': CustomUser.USER_TYPE_CHOICES,
        'account_statuses': CustomUser.ACCOUNT_STATUS_CHOICES,
        'current_filters': {
            'user_type': user_type,
            'verification_status': verification_status,
            'account_status': account_status,
            'search': search_query,
        },
        'total_users': users.count(),
    }
    return render(request, 'admin_panel/user_management.html', context)

@admin_required
def user_detail(request, user_id):
    """Detailed view of a specific user"""
    user = get_object_or_404(CustomUser, id=user_id)
    profile_extension = getattr(user, 'userprofileextension', None)

    context = {
        'user': user,
        'profile_extension': profile_extension,
        'payments': user.payments.all().order_by('-payment_date')[:10] if hasattr(user, 'payments') else [],
        'suspension_info': user.get_suspension_info(),
    }

    return render(request, 'admin_panel/user_detail.html', context)


@admin_required
@require_POST
def suspend_user(request, user_id):
    """Suspend a user account"""
    user = get_object_or_404(CustomUser, id=user_id)

    if user.is_staff or user.is_superuser:
        return JsonResponse({'success': False, 'message': 'Cannot suspend admin users'})

    duration_days = int(request.POST.get('duration', 7))
    reason = request.POST.get('reason', 'Administrative action')

    user.suspend_account(duration_days, reason)
    messages.success(request, f'User {user.username} has been suspended for {duration_days} days.')

    return JsonResponse({
        'success': True,
        'message': f'User suspended for {duration_days} days',
        'new_status': 'suspended'
    })


@admin_required
@require_POST
def unsuspend_user(request, user_id):
    """Unsuspend a user account"""
    user = get_object_or_404(CustomUser, id=user_id)
    user.unsuspend_account()
    messages.success(request, f'User {user.username} has been unsuspended.')

    return JsonResponse({
        'success': True,
        'message': 'User account reactivated',
        'new_status': 'active'
    })


@admin_required
@require_POST
def delete_user(request, user_id):
    """Permanently delete a user account"""
    user = get_object_or_404(CustomUser, id=user_id)

    if user.is_staff or user.is_superuser:
        return JsonResponse({'success': False, 'message': 'Cannot delete admin users'})

    if request.user == user:
        return JsonResponse({'success': False, 'message': 'Cannot delete your own account'})

    username = user.username
    user.delete()
    messages.success(request, f'User {username} has been permanently deleted.')

    return JsonResponse({
        'success': True,
        'message': f'User {username} deleted successfully',
        'redirect': '/admin-panel/users/'
    })


@admin_required
@require_POST
def verify_user(request, user_id):
    """Verify a user account"""
    user = get_object_or_404(CustomUser, id=user_id)
    user.is_verified = True
    user.save()
    messages.success(request, f'User {user.username} has been verified.')

    return JsonResponse({
        'success': True,
        'message': 'User verified successfully',
        'new_status': 'verified'
    })



@admin_required
@require_POST
def bulk_action(request):
    """Handle bulk actions on multiple users"""
    action = request.POST.get('action')
    user_ids = request.POST.getlist('user_ids')

    print(f"DEBUG: Action: {action}, User IDs: {user_ids}")  # Debug line

    if not user_ids:
        return JsonResponse({
            'success': False,
            'message': 'No users selected'
        })

    # Exclude staff users from bulk actions for safety
    users = CustomUser.objects.filter(id__in=user_ids).exclude(is_staff=True)
    selected_count = len(user_ids)
    safe_count = users.count()

    print(f"DEBUG: Selected: {selected_count}, Safe: {safe_count}")  # Debug line

    if selected_count != safe_count:
        staff_excluded = selected_count - safe_count
        if safe_count == 0:
            return JsonResponse({
                'success': False,
                'message': f'Cannot perform bulk actions on admin users. {staff_excluded} admin users were excluded.'
            })

    if action == 'verify':
        users.update(is_verified=True)
        message = f'{safe_count} users verified successfully'

    elif action == 'suspend':
        duration = int(request.POST.get('duration', 7))
        reason = request.POST.get('reason', 'Bulk administrative action')

        from datetime import timedelta
        suspended_until = timezone.now() + timedelta(days=duration)

        users.update(
            account_status='suspended',
            suspended_until=suspended_until,
            suspension_reason=reason
        )
        message = f'{safe_count} users suspended for {duration} days'

    elif action == 'delete':
        usernames = list(users.values_list('username', flat=True))
        users.delete()
        message = f'{safe_count} users deleted successfully: {", ".join(usernames[:3])}{"..." if len(usernames) > 3 else ""}'

    else:
        return JsonResponse({
            'success': False,
            'message': 'Invalid action'
        })

    if selected_count != safe_count:
        staff_excluded = selected_count - safe_count
        message += f' ({staff_excluded} admin users were skipped for safety)'

    return JsonResponse({
        'success': True,
        'message': message
    })



@admin_required
def register_investor(request):
    if request.method == 'POST':
        form = InvestorRegistrationForm(request.POST)
        if form.is_valid():
            investor = form.save(commit=False)
            investor.user_type = 'investor'
            investor.is_verified = True
            investor.set_password(form.cleaned_data['password1'])
            investor.save()
            messages.success(request, f'Investor {investor.username} registered successfully!')
            return redirect('admin_panel:user_management')
    else:
        form = InvestorRegistrationForm()

    return render(request, 'admin_panel/register_investor.html', {'form': form})


@admin_required
@require_POST
def verify_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    user.is_verified = True
    user.save()
    messages.success(request, f'User {user.username} has been verified!')
    return JsonResponse({'success': True})


@admin_required
def pitch_management(request):
    pitches = IdeaPitch.objects.all().order_by('-submitted_at')

    # Filter options
    status = request.GET.get('status')
    if status:
        pitches = pitches.filter(status=status)

    context = {
        'pitches': pitches,
        'selected_status': status,
    }
    return render(request, 'admin_panel/pitch_management.html', context)


@admin_required
def review_pitch(request, pitch_id):
    pitch = get_object_or_404(IdeaPitch, id=pitch_id)

    if request.method == 'POST':
        form = PitchReviewForm(request.POST, instance=pitch)
        if form.is_valid():
            pitch = form.save(commit=False)
            pitch.reviewed_by = request.user
            pitch.reviewed_at = timezone.now()
            pitch.save()

            action = 'approved' if pitch.status == 'approved' else 'rejected'
            messages.success(request, f'Pitch has been {action}!')
            return redirect('admin_panel:pitch_management')
    else:
        form = PitchReviewForm(instance=pitch)

    context = {
        'pitch': pitch,
        'form': form,
    }
    return render(request, 'admin_panel/review_pitch.html', context)


@admin_required
def payment_management(request):
    payments = SubscriptionPayment.objects.all().order_by('-payment_date')

    # Filter options
    status = request.GET.get('status')
    if status:
        payments = payments.filter(status=status)

    context = {
        'payments': payments,
        'selected_status': status,
    }
    return render(request, 'admin_panel/payment_management.html', context)


# ENHANCED JOB MANAGEMENT SYSTEM

# Replace your job_management function in admin_panel/views.py with this corrected version:

@admin_required
def job_management(request):
    """Enhanced job management dashboard with analytics and advanced filtering"""

    # Get filter parameters
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    industry = request.GET.get('industry', '')
    job_type = request.GET.get('job_type', '')
    per_page = int(request.GET.get('per_page', 25))

    # FIXED: Base queryset - use correct related name
    jobs = JobPosting.objects.select_related('poster').prefetch_related('applications')

    # Apply filters
    if search:
        jobs = jobs.filter(
            Q(title__icontains=search) |
            Q(company_name__icontains=search) |
            Q(description__icontains=search) |
            Q(poster__username__icontains=search)
        )

    if status == 'active':
        jobs = jobs.filter(is_active=True)
    elif status == 'inactive':
        jobs = jobs.filter(is_active=False)
    elif status == 'expired':
        # Check if application deadline has passed
        jobs = jobs.filter(application_deadline__lte=timezone.now())

    if industry:
        jobs = jobs.filter(industry=industry)

    if job_type:
        jobs = jobs.filter(job_type=job_type)

    # Order by creation date (newest first)
    jobs = jobs.order_by('-created_at')

    # Pagination
    paginator = Paginator(jobs, per_page)
    page_number = request.GET.get('page')
    jobs_page = paginator.get_page(page_number)

    # Calculate analytics
    analytics = calculate_job_analytics()

    # Chart data
    chart_data = generate_chart_data()

    # Check if this is an AJAX request for auto-refresh
    if request.GET.get('ajax'):
        return JsonResponse({
            'total_jobs': analytics['total_jobs'],
            'active_jobs': analytics['active_jobs'],
            'total_applications': analytics['total_applications'],
            'avg_applications': analytics['avg_applications']
        })

    context = {
        'jobs': jobs_page,
        'total_jobs': analytics['total_jobs'],
        'active_jobs': analytics['active_jobs'],
        'total_applications': analytics['total_applications'],
        'avg_applications': analytics['avg_applications'],
        'applications_chart_labels': json.dumps(chart_data['applications_labels']),
        'applications_chart_data': json.dumps(chart_data['applications_data']),
        'industry_chart_labels': json.dumps(chart_data['industry_labels']),
        'industry_chart_data': json.dumps(chart_data['industry_data']),
        'job_type_choices': JobPosting.JOB_TYPE_CHOICES,
        'industry_choices': JobPosting.INDUSTRY_CHOICES,
        'selected_status': status,
        'selected_job_type': job_type,
        'selected_industry': industry,
        'search_query': search,
    }

    return render(request, 'admin_panel/job_management.html', context)


# Also fix the calculate_job_analytics function:
def calculate_job_analytics():
    """Calculate job-related analytics"""
    total_jobs = JobPosting.objects.count()
    active_jobs = JobPosting.objects.filter(is_active=True).count()

    total_applications = JobApplication.objects.count()

    # FIXED: Calculate average applications per job using correct related name
    jobs_with_apps = JobPosting.objects.annotate(
        app_count=Count('applications')  # Changed from 'jobapplication' to 'applications'
    ).aggregate(avg=Avg('app_count'))['avg'] or 0

    return {
        'total_jobs': total_jobs,
        'active_jobs': active_jobs,
        'total_applications': total_applications,
        'avg_applications': round(jobs_with_apps, 1)
    }
def generate_chart_data():
    """Generate data for charts"""
    # Applications trend for last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=29)

    applications_labels = []
    applications_data = []

    current_date = start_date
    while current_date <= end_date:
        applications_count = JobApplication.objects.filter(
            applied_at__date=current_date
        ).count()

        applications_labels.append(current_date.strftime('%m/%d'))
        applications_data.append(applications_count)
        current_date += timedelta(days=1)

    # Industry distribution
    industry_data = JobPosting.objects.values('industry').annotate(
        count=Count('id')
    ).order_by('-count')[:6]

    industry_labels = []
    industry_counts = []

    for item in industry_data:
        industry_labels.append(dict(JobPosting.INDUSTRY_CHOICES).get(item['industry'], 'Unknown'))
        industry_counts.append(item['count'])

    return {
        'applications_labels': applications_labels,
        'applications_data': applications_data,
        'industry_labels': industry_labels,
        'industry_data': industry_counts
    }


@admin_required
@require_http_methods(["POST"])
def toggle_job_status(request, job_id):
    """Enhanced toggle job active status with better response"""
    try:
        job = get_object_or_404(JobPosting, id=job_id)
        job.is_active = not job.is_active
        job.save()

        status = "activated" if job.is_active else "deactivated"
        messages.success(request, f'Job "{job.title}" has been {status}!')

        return JsonResponse({
            'success': True,
            'message': f'Job {status} successfully',
            'new_status': job.is_active
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@admin_required
@require_http_methods(["DELETE"])
def delete_job(request, job_id):
    """Enhanced delete job with better error handling"""
    try:
        job = get_object_or_404(JobPosting, id=job_id)
        job_title = job.title
        job.delete()

        return JsonResponse({
            'success': True,
            'message': f'Job "{job_title}" deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@admin_required
@require_http_methods(["POST"])
def bulk_job_action(request):
    """Handle bulk actions on jobs"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        job_ids = data.get('job_ids', [])

        if not job_ids:
            return JsonResponse({
                'success': False,
                'message': 'No jobs selected'
            }, status=400)

        jobs = JobPosting.objects.filter(id__in=job_ids)
        count = jobs.count()

        if action == 'activate':
            jobs.update(is_active=True)
            message = f'{count} job(s) activated successfully'
        elif action == 'deactivate':
            jobs.update(is_active=False)
            message = f'{count} job(s) deactivated successfully'
        elif action == 'delete':
            jobs.delete()
            message = f'{count} job(s) deleted successfully'
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid action'
            }, status=400)

        return JsonResponse({
            'success': True,
            'message': message
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@admin_required
def export_jobs(request):
    """Export jobs data to CSV"""
    # Get same filters as main view
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    industry = request.GET.get('industry', '')
    job_type = request.GET.get('job_type', '')

    # Apply same filtering logic
    jobs = JobPosting.objects.select_related('poster')

    if search:
        jobs = jobs.filter(
            Q(title__icontains=search) |
            Q(company_name__icontains=search) |
            Q(description__icontains=search) |
            Q(poster__username__icontains=search)
        )

    if status == 'active':
        jobs = jobs.filter(is_active=True)
    elif status == 'inactive':
        jobs = jobs.filter(is_active=False)
    elif status == 'expired':
        jobs = jobs.filter(application_deadline__lte=timezone.now())

    if industry:
        jobs = jobs.filter(industry=industry)

    if job_type:
        jobs = jobs.filter(job_type=job_type)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="jobs_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Title', 'Company', 'Industry', 'Job Type', 'Location',
        'Salary Min', 'Salary Max', 'Remote OK', 'Applications Count',
        'Views Count', 'Is Active', 'Posted By', 'Created At', 'Application Deadline'
    ])

    for job in jobs:
        # Get application count for this job
        app_count = JobApplication.objects.filter(job=job).count()

        writer.writerow([
            str(job.id),
            job.title,
            job.company_name,
            job.get_industry_display(),
            job.get_job_type_display(),
            job.location,
            getattr(job, 'salary_min', '') or '',
            getattr(job, 'salary_max', '') or '',
            'Yes' if getattr(job, 'remote_ok', False) else 'No',
            app_count,
            getattr(job, 'views_count', 0),
            'Yes' if job.is_active else 'No',
            job.poster.username,
            job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            job.application_deadline.strftime('%Y-%m-%d %H:%M:%S') if job.application_deadline else ''
        ])

    return response


@admin_required
def job_applications_list(request, job_id):
    """Enhanced view applications for a specific job"""
    job = get_object_or_404(JobPosting, id=job_id)

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    per_page = int(request.GET.get('per_page', 25))

    # FIXED: Get applications using correct field name
    applications = JobApplication.objects.filter(job_posting=job).select_related('applicant').order_by('-applied_at')

    # Apply filters
    if status_filter:
        applications = applications.filter(status=status_filter)

    if search:
        applications = applications.filter(
            Q(applicant__first_name__icontains=search) |
            Q(applicant__last_name__icontains=search) |
            Q(applicant__email__icontains=search) |
            Q(cover_letter__icontains=search)
        )

    # Pagination
    paginator = Paginator(applications, per_page)
    page_number = request.GET.get('page')
    applications_page = paginator.get_page(page_number)

    # FIXED: Application status statistics
    status_stats = JobApplication.objects.filter(job_posting=job).values('status').annotate(count=Count('id'))

    context = {
        'job': job,
        'applications': applications_page,
        'status_stats': status_stats,
        'total_applications': applications.count()
    }

    return render(request, 'admin_panel/enhanced_job_applications.html', context)


@admin_required
@require_http_methods(["POST"])
def update_application_status(request, application_id):
    """Update application status"""
    try:
        application = get_object_or_404(JobApplication, id=application_id)
        data = json.loads(request.body)
        new_status = data.get('status')

        if new_status not in dict(JobApplication.STATUS_CHOICES):
            return JsonResponse({
                'success': False,
                'message': 'Invalid status'
            }, status=400)

        application.status = new_status
        # Add these fields if they exist in your model
        if hasattr(application, 'status_updated_by'):
            application.status_updated_by = request.user
        if hasattr(application, 'status_updated_at'):
            application.status_updated_at = timezone.now()
        application.save()

        # TODO: Send notification to applicant about status change

        return JsonResponse({
            'success': True,
            'message': f'Application status updated to {application.get_status_display()}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


# EXISTING VIEWS (PRESERVED FOR BACKWARD COMPATIBILITY)

@admin_required
def job_detail_admin(request, job_id):
    """View job details in admin panel - redirects to enhanced applications view"""
    return redirect('admin_panel:job_applications', job_id=job_id)


@admin_required
@require_POST
def feature_job(request, job_id):
    """Toggle job featured status"""
    job = get_object_or_404(JobPosting, id=job_id)
    job.is_featured = not job.is_featured
    job.save()

    status = "featured" if job.is_featured else "unfeatured"
    messages.success(request, f'Job "{job.title}" has been {status}!')
    return JsonResponse({'success': True, 'is_featured': job.is_featured})


@admin_required
def application_management(request):
    """Manage all job applications across all jobs"""
    # Get filter parameters
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')

    # Base queryset for ALL applications - make sure to include job_posting
    applications = JobApplication.objects.select_related(
        'applicant', 'applicant__userprofileextension', 'job_posting'
    ).order_by('-applied_at')

    # Apply filters
    if search:
        applications = applications.filter(
            Q(applicant__first_name__icontains=search) |
            Q(applicant__last_name__icontains=search) |
            Q(applicant__email__icontains=search) |
            Q(applicant__username__icontains=search) |
            Q(job_posting__title__icontains=search) |
            Q(job_posting__company_name__icontains=search)
        )

    if status:
        applications = applications.filter(status=status)

    # Pagination
    paginator = Paginator(applications, 25)
    page_number = request.GET.get('page')
    applications_page = paginator.get_page(page_number)

    # Calculate statistics based on your actual status choices
    total_applications = JobApplication.objects.count()
    pending_applications = JobApplication.objects.filter(status='pending').count()
    reviewing_applications = JobApplication.objects.filter(status='reviewing').count()
    shortlisted_applications = JobApplication.objects.filter(status='shortlisted').count()
    interview_scheduled_applications = JobApplication.objects.filter(status='interview_scheduled').count()
    hired_applications = JobApplication.objects.filter(status='hired').count()

    context = {
        'page_obj': applications_page,  # This is what the template expects
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'reviewing_applications': reviewing_applications,
        'shortlisted_applications': shortlisted_applications,
        'interview_scheduled_applications': interview_scheduled_applications,
        'hired_applications': hired_applications,
        'search_query': search,
        'selected_status': status,
    }

    # Make sure you're using the NEW template
    return render(request, 'admin_panel/application_management.html', context)

@admin_required
def application_detail_admin(request, application_id):
    """View application details in admin panel"""
    application = get_object_or_404(JobApplication, id=application_id)

    context = {
        'application': application,
        'portfolio_links': getattr(application, 'get_portfolio_links_list', lambda: [])(),
    }
    return render(request, 'admin_panel/application_detail.html', context)


@admin_required
def job_analytics(request):
    """Job analytics and statistics"""

    from django.db.models import Avg, Sum, Count
    from datetime import datetime, timedelta

    # Date range for analytics (default: last 30 days)
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    # Job statistics
    job_stats = {
        'total_jobs': JobPosting.objects.count(),
        'active_jobs': JobPosting.objects.filter(is_active=True).count(),
        'featured_jobs': JobPosting.objects.filter(is_featured=True).count() if hasattr(JobPosting,
                                                                                        'is_featured') else 0,
        'recent_jobs': JobPosting.objects.filter(created_at__gte=start_date).count(),
    }

    # Application statistics
    app_stats = {
        'total_applications': JobApplication.objects.count(),
        'pending_applications': JobApplication.objects.filter(status='pending').count(),
        'shortlisted_applications': JobApplication.objects.filter(status='shortlisted').count(),
        'hired_applications': JobApplication.objects.filter(status='hired').count(),
        'recent_applications': JobApplication.objects.filter(applied_at__gte=start_date).count(),
    }

    # User statistics
    user_stats = {
        'total_job_seekers': CustomUser.objects.filter(user_type='job_seeker').count(),
        'verified_job_seekers': CustomUser.objects.filter(user_type='job_seeker', is_verified=True).count(),
        'job_posters': CustomUser.objects.filter(job_postings__isnull=False).distinct().count(),
    }

    # Top industries and job types
    top_industries = JobPosting.objects.values('industry').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    top_job_types = JobPosting.objects.values('job_type').annotate(
        count=Count('id')
    ).order_by('-count')[:10]

    # Most active job posters
    top_posters = CustomUser.objects.filter(
        job_postings__isnull=False
    ).annotate(
        job_count=Count('job_postings')
    ).order_by('-job_count')[:10]

    # Application success rates by status
    application_status_distribution = JobApplication.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')

    context = {
        'job_stats': job_stats,
        'app_stats': app_stats,
        'user_stats': user_stats,
        'top_industries': top_industries,
        'top_job_types': top_job_types,
        'top_posters': top_posters,
        'application_status_distribution': application_status_distribution,
        'selected_days': days,
    }
    return render(request, 'admin_panel/job_analytics.html', context)


@admin_required
def job_seeker_management(request):
    """Manage job seekers specifically"""
    job_seekers = CustomUser.objects.filter(user_type='job_seeker').select_related('userprofileextension').order_by(
        '-created_at')

    # Filter options
    verification_status = request.GET.get('verification_status')
    if verification_status == 'verified':
        job_seekers = job_seekers.filter(is_verified=True)
    elif verification_status == 'pending':
        job_seekers = job_seekers.filter(is_verified=False)

    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        job_seekers = job_seekers.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(userprofileextension__first_name__icontains=search_query) |
            Q(userprofileextension__last_name__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(job_seekers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get application statistics for each job seeker
    for job_seeker in page_obj:
        job_seeker.application_count = JobApplication.objects.filter(applicant=job_seeker).count()
        job_seeker.saved_jobs_count = JobSavedJob.objects.filter(user=job_seeker).count()
        job_seeker.alerts_count = JobAlert.objects.filter(user=job_seeker).count()

    context = {
        'page_obj': page_obj,
        'selected_verification_status': verification_status,
        'search_query': search_query,
    }
    return render(request, 'admin_panel/job_seeker_management.html', context)


@admin_required
def job_seeker_detail(request, user_id):
    """View job seeker profile and activity"""
    job_seeker = get_object_or_404(CustomUser, id=user_id, user_type='job_seeker')

    # Get job seeker's activity
    applications = JobApplication.objects.filter(applicant=job_seeker).select_related('job').order_by(
        '-applied_at')[:10]
    saved_jobs = JobSavedJob.objects.filter(user=job_seeker).select_related('job').order_by('-saved_at')[:10]
    job_alerts = JobAlert.objects.filter(user=job_seeker).order_by('-created_at')[:5]

    # Statistics
    stats = {
        'total_applications': JobApplication.objects.filter(applicant=job_seeker).count(),
        'pending_applications': JobApplication.objects.filter(applicant=job_seeker, status='pending').count(),
        'shortlisted_applications': JobApplication.objects.filter(applicant=job_seeker, status='shortlisted').count(),
        'total_saved_jobs': JobSavedJob.objects.filter(user=job_seeker).count(),
        'active_alerts': JobAlert.objects.filter(user=job_seeker, is_active=True).count(),
    }

    context = {
        'job_seeker': job_seeker,
        'applications': applications,
        'saved_jobs': saved_jobs,
        'job_alerts': job_alerts,
        'stats': stats,
    }
    return render(request, 'admin_panel/job_seeker_detail.html', context)


@admin_required
def application_details(request, application_id):
    """Get application details for modal display"""
    try:
        application = get_object_or_404(JobApplication, id=application_id)

        data = {
            'success': True,
            'cover_letter': getattr(application, 'cover_letter', ''),
            'experience': getattr(application, 'experience', ''),
            'portfolio_links': getattr(application, 'portfolio_links', ''),
            'applicant_name': application.applicant.get_full_name() or application.applicant.username,
            'applicant_email': application.applicant.email,
            'applied_at': application.applied_at.strftime('%B %d, %Y at %I:%M %p'),
            'status': application.get_status_display(),
        }

        # Add additional fields if they exist in your model
        if hasattr(application, 'skills'):
            data['skills'] = application.skills
        if hasattr(application, 'expected_salary'):
            data['expected_salary'] = application.expected_salary
        if hasattr(application, 'availability'):
            data['availability'] = application.availability

        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)


@admin_required
@require_http_methods(["DELETE"])
def delete_application_admin(request, application_id):
    """Delete a job application (admin function)"""
    try:
        application = get_object_or_404(JobApplication, id=application_id)
        applicant_name = application.applicant.get_full_name() or application.applicant.username
        # FIXED: Use correct field name
        job_title = application.job_posting.title

        application.delete()

        return JsonResponse({
            'success': True,
            'message': f'Application from {applicant_name} for {job_title} deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=400)



@admin_required
def export_applications(request, job_id):
    """Export applications for a specific job to CSV"""
    job = get_object_or_404(JobPosting, id=job_id)

    # Get same filters as applications list view
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    # FIXED: Apply same filtering logic using correct field name
    applications = JobApplication.objects.filter(job_posting=job).select_related('applicant')

    if status_filter:
        applications = applications.filter(status=status_filter)

    if search:
        applications = applications.filter(
            Q(applicant__first_name__icontains=search) |
            Q(applicant__last_name__icontains=search) |
            Q(applicant__email__icontains=search) |
            Q(cover_letter__icontains=search)
        )

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="applications_{job.title}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Application ID', 'Applicant Name', 'Email', 'Phone', 'Status',
        'Applied Date', 'Cover Letter', 'Portfolio Links', 'Location', 'Resume'
    ])

    for application in applications:
        # Get applicant profile info safely
        profile = getattr(application.applicant, 'userprofileextension', None)

        writer.writerow([
            str(application.id),
            application.applicant.get_full_name() or application.applicant.username,
            application.applicant.email,
            profile.phone if profile and hasattr(profile, 'phone') else '',
            application.get_status_display(),
            application.applied_at.strftime('%Y-%m-%d %H:%M:%S'),
            getattr(application, 'cover_letter', '')[:500] + '...' if getattr(application, 'cover_letter', '') and len(getattr(application, 'cover_letter', '')) > 500 else getattr(application, 'cover_letter', ''),
            getattr(application, 'portfolio_links', '')[:200] + '...' if getattr(application, 'portfolio_links', '') and len(getattr(application, 'portfolio_links', '')) > 200 else getattr(application, 'portfolio_links', ''),
            profile.location if profile and hasattr(profile, 'location') else '',
            'Yes' if getattr(application, 'custom_resume', None) else 'No'
        ])

    return response


from payments.models import PlatformSettings
from django.core.cache import cache


# Then add this view function anywhere in the file (suggested: after payment_management)

@admin_required
def platform_settings(request):
    """Manage platform-wide settings like registration and subscription fees"""

    # Get or create settings
    settings = PlatformSettings.get_settings()

    if request.method == 'POST':
        try:
            # Get new values from form
            registration_fee = request.POST.get('registration_fee')
            subscription_fee = request.POST.get('subscription_fee')

            # Validate
            if not registration_fee or not subscription_fee:
                messages.error(request, 'Both fees are required')
                return redirect('admin_panel:platform_settings')

            # Convert to Decimal and validate minimum
            from decimal import Decimal, InvalidOperation

            try:
                reg_fee = Decimal(registration_fee)
                sub_fee = Decimal(subscription_fee)

                if reg_fee < Decimal('1.00'):
                    messages.error(request, 'Registration fee must be at least KES 1.00')
                    return redirect('admin_panel:platform_settings')

                if sub_fee < Decimal('1.00'):
                    messages.error(request, 'Subscription fee must be at least KES 1.00')
                    return redirect('admin_panel:platform_settings')

            except InvalidOperation:
                messages.error(request, 'Invalid fee amount. Please enter valid numbers.')
                return redirect('admin_panel:platform_settings')

            # Update settings
            settings.registration_fee = reg_fee
            settings.subscription_fee = sub_fee
            settings.updated_by = request.user.username
            settings.save()

            # Clear cache
            cache.delete('platform_settings')

            messages.success(request,
                             f'Platform settings updated successfully! Registration: KES {reg_fee}, Subscription: KES {sub_fee}')
            return redirect('admin_panel:platform_settings')

        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
            return redirect('admin_panel:platform_settings')

    # GET request - show form
    context = {
        'settings': settings,
        'recent_changes': PlatformSettings.objects.all().order_by('-updated_at')[:10]
    }
    return render(request, 'admin_panel/platform_settings.html', context)


@admin_required
def view_settings_history(request):
    """View history of settings changes"""
    all_settings = PlatformSettings.objects.all().order_by('-updated_at')

    # Pagination
    paginator = Paginator(all_settings, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
    }
    return render(request, 'admin_panel/settings_history.html', context)


@admin_required
def financial_analysis(request):
    """Financial analysis dashboard with revenue metrics and visualizations"""
    from django.db.models import Sum, Count, Q
    from decimal import Decimal

    # Get all payments
    all_payments = SubscriptionPayment.objects.all()

    # Revenue by status
    completed_payments = all_payments.filter(status='completed')
    pending_payments = all_payments.filter(status='pending')
    failed_payments = all_payments.filter(status='failed')

    # Calculate totals
    total_revenue = completed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    pending_revenue = pending_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    failed_revenue = failed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Revenue by transaction type
    registration_revenue = completed_payments.filter(
        transaction_type='REGISTRATION'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    subscription_revenue = completed_payments.filter(
        transaction_type='SUBSCRIPTION'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Count statistics
    total_transactions = all_payments.count()
    completed_count = completed_payments.count()
    pending_count = pending_payments.count()
    failed_count = failed_payments.count()

    registration_count = all_payments.filter(transaction_type='REGISTRATION').count()
    subscription_count = all_payments.filter(transaction_type='SUBSCRIPTION').count()

    # Calculate success rate
    success_rate = (completed_count / total_transactions * 100) if total_transactions > 0 else 0

    # Average transaction value
    avg_transaction = (total_revenue / completed_count) if completed_count > 0 else Decimal('0.00')

    # Recent transactions
    recent_transactions = all_payments.select_related('user').order_by('-payment_date')[:10]

    # Prepare data for charts (JSON format for Chart.js)
    status_chart_data = {
        'labels': ['Completed', 'Pending', 'Failed'],
        'data': [completed_count, pending_count, failed_count],
        'colors': ['#10b981', '#f59e0b', '#ef4444']
    }

    type_chart_data = {
        'labels': ['Registration', 'Subscription'],
        'data': [float(registration_revenue), float(subscription_revenue)],
        'colors': ['#3b82f6', '#8b5cf6']
    }

    context = {
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'failed_revenue': failed_revenue,
        'registration_revenue': registration_revenue,
        'subscription_revenue': subscription_revenue,
        'total_transactions': total_transactions,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'failed_count': failed_count,
        'registration_count': registration_count,
        'subscription_count': subscription_count,
        'success_rate': round(success_rate, 1),
        'avg_transaction': avg_transaction,
        'recent_transactions': recent_transactions,
        'status_chart_data': json.dumps(status_chart_data),
        'type_chart_data': json.dumps(type_chart_data),
    }

    return render(request, 'admin_panel/financial_analysis.html', context)