from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponse
from django.utils import timezone
from django.utils.timezone import localtime
from datetime import timedelta
import calendar as cal_module

from .models import Deadline, Conflict, DeadlineReminder, TelemetryEvent
from .forms import DeadlineForm
from .utils import (
    log_event,
    detect_conflicts_for_user,
    schedule_reminders,
    compute_smart_plan,
    get_analytics_data,
    get_calendar_data,
)


# ── Immediate SMS on deadline creation ───────────────────────────────────────

def _send_confirmation_sms(user, deadline):
    """
    Fires an immediate SMS the moment a deadline is saved.
    Message tells the user what was created and how far away it is.
    Silently no-ops when Twilio is unconfigured or the user has no phone.
    """
    try:
        from dashboard.models import UserProfile
        from .reminders import _send_sms
        from django.utils import timezone

        profile = UserProfile.objects.get(user=user)
        phone = (profile.phone_number or "").strip()
        if not phone:
            return

        hours_left = (deadline.deadline_at - timezone.now()).total_seconds() / 3600
        hours_left = max(hours_left, 0)

        if hours_left >= 48:
            time_str = str(round(hours_left / 24, 1)) + " days"
        elif hours_left >= 1:
            time_str = str(round(hours_left, 1)) + " hours"
        else:
            time_str = str(round(hours_left * 60)) + " minutes"

        lines = [
            "[ScholarSpace] Deadline created!",
            "You have '" + deadline.title + "' due in " + time_str + ".",
            "Priority: " + deadline.get_priority_display()
            + " | Est. work: " + str(deadline.est_hours) + "h"
            + " | Type: " + deadline.get_type_display() + ".",
            "Reminders will arrive at 72h, 24h and 1h before the deadline.",
        ]
        _send_sms(phone, chr(10).join(lines))

    except Exception:
        pass



# ── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    from .models import Deadline, Conflict
    from django.utils import timezone
    from datetime import timedelta
    
    # Get statistics - handle unauthenticated users
    if request.user.is_authenticated:
        total_tasks = Deadline.objects.filter(user=request.user).count()
        conflicts = Conflict.objects.filter(user=request.user, is_resolved=False).count()
        
        # Tasks due in next 72 hours
        now = timezone.now()
        due_72h = Deadline.objects.filter(
            user=request.user,
            deadline_at__gte=now,
            deadline_at__lte=now + timedelta(hours=72),
            is_completed=False
        ).count()
    else:
        total_tasks = 0
        conflicts = 0
        due_72h = 0
    
    return render(request, "manage_work/dashboard.html", {
        "mw_total_tasks": total_tasks,
        "mw_conflicts": conflicts,
        "mw_due_72h": due_72h,
    })


# ── Add Deadline ─────────────────────────────────────────────────────────────

@login_required
def add_deadline_view(request):
    if request.method == "POST":
        form = DeadlineForm(request.POST)
        if form.is_valid():
            deadline = form.save(commit=False)
            deadline.user = request.user
            deadline.save()
            detect_conflicts_for_user(request.user)
            schedule_reminders(request.user, deadline)
            log_event(request.user, "deadline_created", deadline=deadline, metadata={
                "title":     deadline.title,
                "type":      deadline.type,
                "priority":  deadline.priority,
                "est_hours": deadline.est_hours,
            })
            # In-app notification
            from dashboard.models import push_notification
            push_notification(
                request.user,
                'Deadline Added',
                f'New deadline "{deadline.title}" ({deadline.get_priority_display()} priority) due {deadline.deadline_at.strftime("%d %b %Y %H:%M")} UTC.',
                notif_type='deadline', icon='event', link='/manage-work/tasks/'
            )

            # Immediate SMS confirmation
            _send_confirmation_sms(request.user, deadline)

            return redirect("manage_work:my_tasks")
    else:
        form = DeadlineForm()
    return render(request, "manage_work/add_deadline.html", {"form": form})


# ── My Tasks ─────────────────────────────────────────────────────────────────

@login_required
def my_tasks_view(request):
    qs = Deadline.objects.filter(user=request.user)

    type_filter     = request.GET.get("type", "")
    priority_filter = request.GET.get("priority", "")
    sort            = request.GET.get("sort", "date")

    if type_filter:
        qs = qs.filter(type=type_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    deadlines = list(qs)

    if sort == "priority":
        deadlines.sort(key=lambda d: (PRIORITY_ORDER.get(d.priority, 9), d.deadline_at))
    else:
        deadlines.sort(key=lambda d: d.deadline_at)

    conflicted_ids = set()
    for c in Conflict.objects.filter(user=request.user, is_resolved=False):
        conflicted_ids.add(c.deadline_a_id)
        conflicted_ids.add(c.deadline_b_id)

    return render(request, "manage_work/my_tasks.html", {
        "deadlines":       deadlines,
        "conflicted_ids":  conflicted_ids,
        "type_filter":     type_filter,
        "priority_filter": priority_filter,
        "sort":            sort,
    })


# ── Calendar ─────────────────────────────────────────────────────────────────

@login_required
def calendar_view(request):
    now   = localtime(timezone.now())
    year  = int(request.GET.get("year",  now.year))
    month = int(request.GET.get("month", now.month))

    if month < 1:  month = 12; year -= 1
    if month > 12: month = 1;  year += 1

    deadlines_by_date, conflict_dates = get_calendar_data(request.user, year, month)
    
    # Create a dictionary with integer day keys for easier template access
    deadlines_by_day = {}
    for date_key, deadline_list in deadlines_by_date.items():
        day = int(date_key.split('-')[2])  # Extract day from YYYY-MM-DD
        deadlines_by_day[day] = deadline_list
    
    cal   = cal_module.monthcalendar(year, month)
    month_name = cal_module.month_name[month]

    prev_month = month - 1 if month > 1  else 12
    prev_year  = year      if month > 1  else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year  = year      if month < 12 else year + 1

    return render(request, "manage_work/calendar.html", {
        "calendar_weeks":    cal,
        "month_name":        month_name,
        "year":              year,
        "month":             month,
        "today":             now.date(),
        "deadlines_by_date": deadlines_by_date,
        "deadlines_by_day":  deadlines_by_day,
        "conflict_dates":    conflict_dates,
        "prev_month":        prev_month,
        "prev_year":         prev_year,
        "next_month":        next_month,
        "next_year":         next_year,
    })


# ── Conflicts ────────────────────────────────────────────────────────────────

@login_required
def conflicts_view(request):
    conflicts = Conflict.objects.filter(
        user=request.user, is_resolved=False
    ).select_related("deadline_a", "deadline_b").order_by("-overlap_hours")
    return render(request, "manage_work/conflicts.html", {"conflicts": conflicts})


@login_required
def resolve_conflict_view(request, pk):
    conflict = get_object_or_404(Conflict, pk=pk)
    if conflict.user != request.user:
        return HttpResponseForbidden()
    if request.method == "POST":
        conflict.is_resolved = True
        conflict.save(update_fields=["is_resolved"])
        log_event(request.user, "conflict_resolved", metadata={
            "task_a": conflict.deadline_a.title,
            "task_b": conflict.deadline_b.title,
        })
    return redirect("manage_work:conflicts")


# ── Smart Plan ────────────────────────────────────────────────────────────────

@login_required
def smart_plan_view(request):
    scored = compute_smart_plan(request.user)
    log_event(request.user, "smart_plan_viewed")
    return render(request, "manage_work/smart_plan.html", {"scored_deadlines": scored})


# ── Reminders ─────────────────────────────────────────────────────────────────

@login_required
def reminders_view(request):
    now = timezone.now()
    reminders = DeadlineReminder.objects.filter(
        user=request.user,
        is_sent=False,
        remind_at__gt=now,
    ).select_related("deadline").order_by("remind_at")
    return render(request, "manage_work/reminders.html", {"reminders": reminders})


# ── Analytics ─────────────────────────────────────────────────────────────────

@login_required
def analytics_view(request):
    data = get_analytics_data(request.user)
    log_event(request.user, "analytics_viewed")
    return render(request, "manage_work/analytics.html", {"analytics": data})


# ── Complete ──────────────────────────────────────────────────────────────────

@login_required
def complete_deadline_view(request, pk):
    if request.method != "POST":
        return redirect("manage_work:my_tasks")
    d = _owned_deadline(pk, request.user)
    if isinstance(d, HttpResponseForbidden):
        return d
    d.is_completed = True
    d.save(update_fields=["is_completed"])
    detect_conflicts_for_user(request.user)
    log_event(request.user, "deadline_completed", deadline=d, metadata={"title": d.title})
    return redirect("manage_work:my_tasks")


# ── Delete ────────────────────────────────────────────────────────────────────

@login_required
def delete_deadline_view(request, pk):
    if request.method != "POST":
        return redirect("manage_work:my_tasks")
    d = _owned_deadline(pk, request.user)
    if isinstance(d, HttpResponseForbidden):
        return d
    title = d.title
    d.delete()
    detect_conflicts_for_user(request.user)
    log_event(request.user, "deadline_deleted", metadata={"title": title})
    return redirect("manage_work:my_tasks")


# ── Load sample data ──────────────────────────────────────────────────────────

@login_required
def load_sample_view(request):
    if request.method != "POST":
        return redirect("manage_work:my_tasks")
    now = timezone.now()
    samples = [
        dict(title="OS Assignment 3",       type="assignment", priority="high",     deadline_at=now+timedelta(days=3),  est_hours=10),
        dict(title="Data Structures Exam",  type="exam",       priority="critical", deadline_at=now+timedelta(days=4),  est_hours=8),
        dict(title="Hackathon Project MVP", type="hackathon",  priority="medium",   deadline_at=now+timedelta(days=7),  est_hours=20),
        dict(title="Research Paper Draft",  type="project",    priority="low",      deadline_at=now+timedelta(days=14), est_hours=5),
    ]
    for s in samples:
        d = Deadline.objects.create(user=request.user, **s)
        schedule_reminders(request.user, d)
    detect_conflicts_for_user(request.user)
    return redirect("manage_work:my_tasks")


# ── Clear all ─────────────────────────────────────────────────────────────────

@login_required
def clear_all_view(request):
    if request.method != "POST":
        return redirect("manage_work:my_tasks")
    Deadline.objects.filter(user=request.user).delete()
    return redirect("manage_work:my_tasks")


# ── Telemetry ─────────────────────────────────────────────────────────────────

@login_required
def telemetry_view(request):
    events = TelemetryEvent.objects.filter(
        user=request.user
    ).select_related("deadline").order_by("-occurred_at")[:100]
    return render(request, "manage_work/telemetry.html", {"events": events})


# ── Google Calendar Sync ──────────────────────────────────────────────────────

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import requests

@login_required
@require_http_methods(["POST"])
def sync_google_calendar_view(request):
    """Sync deadlines to Google Calendar."""
    try:
        from django.conf import settings
        
        # Get user's deadlines
        deadlines = Deadline.objects.filter(
            user=request.user, 
            is_completed=False
        ).order_by('deadline_at')
        
        if not deadlines:
            return JsonResponse({
                'success': False,
                'message': 'No deadlines to sync'
            })
        
        # Generate Google Calendar links for each deadline
        calendar_links = []
        for deadline in deadlines:
            # Format dates for Google Calendar URL
            start_time = deadline.deadline_at.strftime('%Y%m%dT%H%M%S')
            end_time = (deadline.deadline_at + timedelta(hours=1)).strftime('%Y%m%dT%H%M%S')
            
            # Create Google Calendar URL
            calendar_url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={deadline.title}&dates={start_time}/{end_time}&details=Priority: {deadline.get_priority_display()}\\nType: {deadline.get_type_display()}\\nNotes: {deadline.notes}&location=Online"
            
            calendar_links.append({
                'title': deadline.title,
                'url': calendar_url,
                'deadline_at': deadline.deadline_at.strftime('%Y-%m-%d %H:%M')
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Generated {len(calendar_links)} calendar links',
            'deadlines': calendar_links
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error syncing to Google Calendar: {str(e)}'
        })


# ── Google Calendar OAuth Integration ────────────────────────────────────────

from django.shortcuts import redirect
from django.contrib import messages
from .google_calendar import GoogleCalendarService
from .models import GoogleCalendarSync

@login_required
def google_calendar_connect_view(request):
    """Initiate Google Calendar OAuth connection."""
    try:
        service = GoogleCalendarService()
        auth_url, state = service.get_authorization_url(request.user)
        
        if auth_url:
            # Store state in session
            request.session['google_calendar_state'] = state
            request.session['google_calendar_user_id'] = request.user.id
            return redirect(auth_url)
        else:
            messages.error(request, "Failed to generate Google Calendar authorization URL.")
            return redirect("manage_work:calendar")
            
    except Exception as e:
        messages.error(request, f"Error connecting to Google Calendar: {str(e)}")
        return redirect("manage_work:calendar")


@login_required
def google_calendar_callback_view(request):
    """Handle Google Calendar OAuth callback."""
    try:
        # Verify state
        state = request.GET.get('state')
        stored_state = request.session.get('google_calendar_state')
        stored_user_id = request.session.get('google_calendar_user_id')
        
        if not state or state != stored_state or stored_user_id != request.user.id:
            messages.error(request, "Invalid OAuth state.")
            return redirect("manage_work:calendar")
        
        # Clear session data
        del request.session['google_calendar_state']
        del request.session['google_calendar_user_id']
        
        # Get authorization code
        code = request.GET.get('code')
        if not code:
            messages.error(request, "Authorization code not found.")
            return redirect("manage_work:calendar")
        
        # Exchange code for tokens
        service = GoogleCalendarService()
        flow = Flow.from_client_config(
            service.client_config,
            scopes=service.SCOPES,
            redirect_uri=service.REDIRECT_URI
        )
        flow.fetch_token(code=code)
        
        # Get credentials
        credentials = flow.credentials
        
        # Store tokens in database
        sync_record, created = GoogleCalendarSync.objects.get_or_create(
            user=request.user,
            defaults={
                'token_data': {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes,
                }
            }
        )
        
        if not created:
            sync_record.token_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes,
            }
            sync_record.save()
        
        # Sync existing deadlines
        service = GoogleCalendarService()
        deadlines = Deadline.objects.filter(user=request.user, is_completed=False)
        synced_count = 0
        
        for deadline in deadlines:
            success, message = service.sync_deadline_to_calendar(request.user, deadline)
            if success:
                synced_count += 1
        
        messages.success(
            request, 
            f"Successfully connected to Google Calendar! Synced {synced_count} deadlines."
        )
        return redirect("manage_work:calendar")
        
    except Exception as e:
        messages.error(request, f"Error connecting to Google Calendar: {str(e)}")
        return redirect("manage_work:calendar")


@login_required
def google_calendar_disconnect_view(request):
    """Disconnect Google Calendar integration."""
    try:
        sync_record = GoogleCalendarSync.objects.filter(user=request.user).first()
        if sync_record:
            sync_record.delete()
            messages.success(request, "Disconnected from Google Calendar.")
        else:
            messages.info(request, "Google Calendar was not connected.")
            
        return redirect("manage_work:calendar")
        
    except Exception as e:
        messages.error(request, f"Error disconnecting Google Calendar: {str(e)}")
        return redirect("manage_work:calendar")


# ── SMS / Notification Settings ───────────────────────────────────────────────

@login_required
def sms_settings_view(request):
    """
    Page where users can set their phone number, send a test SMS,
    and see their upcoming reminders.
    """
    from dashboard.models import UserProfile
    from django.conf import settings as dj_settings

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    twilio_configured = bool(
        getattr(dj_settings, "TWILIO_ACCOUNT_SID", "").strip()
        and getattr(dj_settings, "TWILIO_AUTH_TOKEN", "").strip()
        and getattr(dj_settings, "TWILIO_PHONE_NUMBER", "").strip()
    )

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "update_phone":
            raw = request.POST.get("phone_number", "").strip()
            # E.164 normalisation
            if raw:
                import re as _re
                # Strip spaces, dashes, brackets
                raw = _re.sub(r"[\s\-\.\(\)]", "", raw)
                if not raw.startswith("+"):
                    # 10-digit number with no country code → assume India (+91)
                    if len(raw) == 10 and raw.isdigit():
                        raw = "+91" + raw
                    else:
                        raw = "+" + raw
            profile.phone_number = raw
            profile.save(update_fields=["phone_number"])
            from django.contrib import messages as dj_messages
            dj_messages.success(
                request,
                f"Phone number {'saved: ' + raw if raw else 'cleared.'}"
            )
            # Re-schedule all active deadlines so new channel is picked up
            from .utils import schedule_reminders
            for dl in Deadline.objects.filter(
                user=request.user, is_completed=False
            ):
                schedule_reminders(request.user, dl)
            return redirect("manage_work:sms_settings")

        elif action == "test_sms":
            phone = (profile.phone_number or "").strip()
            from django.contrib import messages as dj_messages
            if not phone:
                dj_messages.error(
                    request,
                    "No phone number saved. Enter one above first."
                )
            elif not twilio_configured:
                dj_messages.error(
                    request,
                    "Twilio is not configured on this server. "
                    "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                    "and TWILIO_PHONE_NUMBER environment variables."
                )
            else:
                from .reminders import _send_sms
                ok = _send_sms(
                    phone,
                    f"[ScholarSpace] Hi {request.user.username}! "
                    f"This is a test SMS. Your deadline reminders are active "
                    f"and will be sent at 72h, 24h, and 1h before each deadline."
                )
                if ok:
                    dj_messages.success(
                        request, f"Test SMS sent successfully to {phone}!"
                    )
                else:
                    dj_messages.error(
                        request,
                        "SMS failed. Check the server logs for the Twilio error."
                    )
            return redirect("manage_work:sms_settings")

        elif action == "clear_sent":
            DeadlineReminder.objects.filter(
                user=request.user, is_sent=True
            ).delete()
            from django.contrib import messages as dj_messages
            dj_messages.success(request, "Sent reminder history cleared.")
            return redirect("manage_work:sms_settings")

    now = timezone.now()
    upcoming = DeadlineReminder.objects.filter(
        user=request.user, is_sent=False, remind_at__gt=now
    ).select_related("deadline").order_by("remind_at")

    sent_history = DeadlineReminder.objects.filter(
        user=request.user, is_sent=True
    ).select_related("deadline").order_by("-sent_at")[:20]

    return render(request, "manage_work/sms_settings.html", {
        "profile":           profile,
        "twilio_configured": twilio_configured,
        "upcoming":          upcoming,
        "sent_history":      sent_history,
    })
