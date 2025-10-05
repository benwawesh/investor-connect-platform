from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone

from .models import JobPosting, JobApplication, JobSavedJob, JobAlert
from .forms import (JobPostingForm, JobApplicationForm, JobSearchForm,
                    JobAlertForm, SavedJobNotesForm, ApplicationStatusUpdateForm)


def job_list(request):
    """Display list of active job postings"""
    jobs = JobPosting.objects.filter(is_active=True).select_related('poster').order_by('-created_at')

    # Simple search if query provided
    search_query = request.GET.get('q')
    if search_query:
        jobs = jobs.filter(
            Q(title__icontains=search_query) |
            Q(company_name__icontains=search_query) |
            Q(skills_required__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(jobs, 12)  # 12 jobs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'total_jobs': jobs.count(),
    }
    return render(request, 'jobs/job_list.html', context)


def job_search(request):
    """Advanced job search with filters"""
    form = JobSearchForm(request.GET or None)
    jobs = JobPosting.objects.filter(is_active=True).select_related('poster')

    if form.is_valid():
        # Apply filters
        if form.cleaned_data.get('keywords'):
            keywords = form.cleaned_data['keywords']
            jobs = jobs.filter(
                Q(title__icontains=keywords) |
                Q(description__icontains=keywords) |
                Q(skills_required__icontains=keywords) |
                Q(company_name__icontains=keywords)
            )

        if form.cleaned_data.get('location'):
            jobs = jobs.filter(location__icontains=form.cleaned_data['location'])

        if form.cleaned_data.get('job_type'):
            jobs = jobs.filter(job_type=form.cleaned_data['job_type'])

        if form.cleaned_data.get('experience_level'):
            jobs = jobs.filter(experience_level=form.cleaned_data['experience_level'])

        if form.cleaned_data.get('industry'):
            jobs = jobs.filter(industry=form.cleaned_data['industry'])

        if form.cleaned_data.get('remote_only'):
            jobs = jobs.filter(remote_ok=True)

        if form.cleaned_data.get('salary_min'):
            jobs = jobs.filter(salary_min__gte=form.cleaned_data['salary_min'])

    # Pagination
    paginator = Paginator(jobs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'form': form,
        'page_obj': page_obj,
        'total_jobs': jobs.count(),
    }
    return render(request, 'jobs/job_search.html', context)


def job_detail(request, job_id):
    """Display job details"""
    job = get_object_or_404(JobPosting, id=job_id, is_active=True)

    # Increment view count
    job.increment_views()

    # Check if user has applied (for job seekers)
    user_applied = False
    user_saved = False
    can_apply = False

    if request.user.is_authenticated:
        if request.user.user_type in ['job_seeker', 'regular']:
            user_applied = JobApplication.objects.filter(job_posting=job, applicant=request.user).exists()
            user_saved = JobSavedJob.objects.filter(job_posting=job, user=request.user).exists()
            can_apply = not user_applied and not job.is_deadline_passed()

    context = {
        'job': job,
        'user_applied': user_applied,
        'user_saved': user_saved,
        'can_apply': can_apply,
        'skills_list': job.get_skills_list(),
    }
    return render(request, 'jobs/job_detail.html', context)


@login_required
def post_job(request):
    """Create a new job posting (employers only)"""
    if not request.user.can_post_jobs:
        messages.error(request, "You don't have permission to post jobs.")
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.poster = request.user
            job.save()
            messages.success(request, "Job posting created successfully!")
            return redirect('jobs:job_detail', job_id=job.id)
    else:
        form = JobPostingForm()
        # Pre-fill company name if available
        if hasattr(request.user, 'company_name') and request.user.company_name:
            form.initial['company_name'] = request.user.company_name

    return render(request, 'jobs/post_job.html', {'form': form})


@login_required
def edit_job(request, job_id):
    """Edit job posting (owner only)"""
    job = get_object_or_404(JobPosting, id=job_id, poster=request.user)

    if request.method == 'POST':
        form = JobPostingForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Job posting updated successfully!")
            return redirect('jobs:job_detail', job_id=job.id)
    else:
        form = JobPostingForm(instance=job)

    return render(request, 'jobs/edit_job.html', {'form': form, 'job': job})


@login_required
def delete_job(request, job_id):
    """Delete job posting (owner only)"""
    job = get_object_or_404(JobPosting, id=job_id, poster=request.user)

    if request.method == 'POST':
        job.is_active = False  # Soft delete
        job.save()
        messages.success(request, "Job posting deleted successfully!")
        return redirect('jobs:my_job_postings')

    return render(request, 'jobs/delete_job.html', {'job': job})


@login_required
def my_job_postings(request):
    """Display user's job postings (employers)"""
    if not request.user.can_post_jobs:
        return HttpResponseForbidden("You don't have permission to view this page.")

    jobs = JobPosting.objects.filter(poster=request.user).annotate(
        total_applications=Count('applications')
    ).order_by('-created_at')

    # Pagination
    paginator = Paginator(jobs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'jobs/my_job_postings.html', {'page_obj': page_obj})


@login_required
def apply_job(request, job_id):
    """Apply for a job (job seekers only)"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        messages.error(request, "Only job seekers can apply for jobs.")
        return redirect('jobs:job_detail', job_id=job_id)

    job = get_object_or_404(JobPosting, id=job_id, is_active=True)

    # Check if already applied
    if JobApplication.objects.filter(job_posting=job, applicant=request.user).exists():
        messages.warning(request, "You have already applied for this job.")
        return redirect('jobs:job_detail', job_id=job_id)

    # Check deadline
    if job.is_deadline_passed():
        messages.error(request, "The application deadline has passed.")
        return redirect('jobs:job_detail', job_id=job_id)

    if request.method == 'POST':
        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save(commit=False)
            application.job_posting = job
            application.applicant = request.user
            application.save()

            # Update job application count
            job.applications_count += 1
            job.save(update_fields=['applications_count'])

            messages.success(request, "Application submitted successfully!")
            return redirect('jobs:job_detail', job_id=job_id)
    else:
        form = JobApplicationForm()

    context = {
        'form': form,
        'job': job,
    }
    return render(request, 'jobs/apply_job.html', context)


@login_required
def my_applications(request):
    """Display user's job applications (job seekers)"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        return HttpResponseForbidden("You don't have permission to view this page.")

    applications = JobApplication.objects.filter(applicant=request.user).select_related(
        'job_posting', 'status_updated_by'
    ).order_by('-applied_at')

    # Pagination
    paginator = Paginator(applications, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'jobs/my_applications.html', {'page_obj': page_obj})


@login_required
def application_detail(request, application_id):
    """View application details"""
    application = get_object_or_404(JobApplication, id=application_id)

    # Check permissions
    if not (application.applicant == request.user or
            application.job_posting.poster == request.user or
            request.user.is_staff):
        return HttpResponseForbidden("You don't have permission to view this application.")

    return render(request, 'jobs/application_detail.html', {'application': application})


@login_required
def withdraw_application(request, application_id):
    """Withdraw job application (applicant only)"""
    application = get_object_or_404(JobApplication, id=application_id, applicant=request.user)

    if request.method == 'POST':
        application.update_status('withdrawn', updated_by=request.user, notes="Withdrawn by applicant")
        messages.success(request, "Application withdrawn successfully.")
        return redirect('jobs:my_applications')

    return render(request, 'jobs/withdraw_application.html', {'application': application})


@login_required
def job_applications(request, job_id):
    """View applications for a job posting (employer only)"""
    job = get_object_or_404(JobPosting, id=job_id, poster=request.user)

    applications = JobApplication.objects.filter(job_posting=job).select_related(
        'applicant', 'status_updated_by'
    ).order_by('-applied_at')

    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        applications = applications.filter(status=status_filter)

    # Pagination
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get status choices for filter
    status_choices = JobApplication.STATUS_CHOICES

    context = {
        'job': job,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': status_choices,
    }
    return render(request, 'jobs/job_applications.html', context)


@login_required
def update_application_status(request, application_id):
    """Update application status (employer only)"""
    application = get_object_or_404(JobApplication, id=application_id)

    # Check permission
    if application.job_posting.poster != request.user:
        return HttpResponseForbidden("You don't have permission to update this application.")

    if request.method == 'POST':
        form = ApplicationStatusUpdateForm(request.POST, instance=application)
        if form.is_valid():
            application = form.save(commit=False)
            application.status_updated_by = request.user
            application.save()
            messages.success(request, "Application status updated successfully!")
            return redirect('jobs:job_applications', job_id=application.job_posting.id)
    else:
        form = ApplicationStatusUpdateForm(instance=application)

    context = {
        'form': form,
        'application': application,
    }
    return render(request, 'jobs/update_application_status.html', context)


@login_required
def save_job(request, job_id):
    """Save/bookmark a job (job seekers only)"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        return JsonResponse({'error': 'Only job seekers can save jobs'}, status=403)

    job = get_object_or_404(JobPosting, id=job_id, is_active=True)
    saved_job, created = JobSavedJob.objects.get_or_create(user=request.user, job_posting=job)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'saved': created,
            'message': 'Job saved!' if created else 'Job already saved'
        })

    if created:
        messages.success(request, "Job saved to your bookmarks!")
    else:
        messages.info(request, "Job is already in your bookmarks.")

    return redirect('jobs:job_detail', job_id=job_id)


@login_required
def unsave_job(request, job_id):
    """Remove job from saved list"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        return JsonResponse({'error': 'Only job seekers can unsave jobs'}, status=403)

    job = get_object_or_404(JobPosting, id=job_id)
    deleted = JobSavedJob.objects.filter(user=request.user, job_posting=job).delete()[0]

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'unsaved': deleted > 0,
            'message': 'Job removed from bookmarks!' if deleted > 0 else 'Job was not saved'
        })

    if deleted > 0:
        messages.success(request, "Job removed from bookmarks!")

    return redirect('jobs:job_detail', job_id=job_id)


@login_required
def saved_jobs(request):
    """Display user's saved jobs"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        return HttpResponseForbidden("You don't have permission to view this page.")

    saved_jobs_list = JobSavedJob.objects.filter(user=request.user).select_related(
        'job_posting'
    ).order_by('-saved_at')

    # Pagination
    paginator = Paginator(saved_jobs_list, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'jobs/saved_jobs.html', {'page_obj': page_obj})


@login_required
def job_alerts(request):
    """Display user's job alerts"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        return HttpResponseForbidden("You don't have permission to view this page.")

    alerts = JobAlert.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'jobs/job_alerts.html', {'alerts': alerts})


@login_required
def create_job_alert(request):
    """Create a new job alert"""
    if request.user.user_type not in ['job_seeker', 'regular']:
        return HttpResponseForbidden("You don't have permission to create job alerts.")

    if request.method == 'POST':
        form = JobAlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            messages.success(request, "Job alert created successfully!")
            return redirect('jobs:job_alerts')
    else:
        form = JobAlertForm()

    return render(request, 'jobs/create_job_alert.html', {'form': form})


@login_required
def edit_job_alert(request, alert_id):
    """Edit job alert"""
    alert = get_object_or_404(JobAlert, id=alert_id, user=request.user)

    if request.method == 'POST':
        form = JobAlertForm(request.POST, instance=alert)
        if form.is_valid():
            form.save()
            messages.success(request, "Job alert updated successfully!")
            return redirect('jobs:job_alerts')
    else:
        form = JobAlertForm(instance=alert)

    return render(request, 'jobs/edit_job_alert.html', {'form': form, 'alert': alert})


@login_required
def delete_job_alert(request, alert_id):
    """Delete job alert"""
    alert = get_object_or_404(JobAlert, id=alert_id, user=request.user)

    if request.method == 'POST':
        alert.delete()
        messages.success(request, "Job alert deleted successfully!")
        return redirect('jobs:job_alerts')

    return render(request, 'jobs/delete_job_alert.html', {'alert': alert})


@login_required
def toggle_job_alert(request, alert_id):
    """Toggle job alert active status"""
    alert = get_object_or_404(JobAlert, id=alert_id, user=request.user)

    alert.is_active = not alert.is_active
    alert.save()

    status = "activated" if alert.is_active else "deactivated"
    messages.success(request, f"Job alert {status}!")

    return redirect('jobs:job_alerts')