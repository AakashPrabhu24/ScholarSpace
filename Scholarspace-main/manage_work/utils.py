from django.utils import timezone
from django.utils.timezone import localtime
from datetime import timedelta, timezone as dt_timezone


# ── Telemetry ────────────────────────────────────────────────────────────────

def log_event(user, event_type, deadline=None, metadata=None):
    """Write one TelemetryEvent row. Never raises."""
    from .models import TelemetryEvent
    try:
        TelemetryEvent.objects.create(
            user=user,
            event_type=event_type,
            deadline=deadline,
            metadata=metadata or {},
        )
    except Exception:
        pass


# ── Conflict detection ───────────────────────────────────────────────────────

def detect_conflicts_for_user(user):
    """
    Recalculate all unresolved conflicts for a user.
    Prep window = [deadline_at - est_hours, deadline_at].
    Severity: <2h=mild | 2-6h=moderate | >6h=critical.
    Resolved conflicts are preserved and not re-detected.
    """
    from .models import Deadline, Conflict

    now = timezone.now()

    resolved_pairs = set()
    for c in Conflict.objects.filter(user=user, is_resolved=True):
        resolved_pairs.add((c.deadline_a_id, c.deadline_b_id))
        resolved_pairs.add((c.deadline_b_id, c.deadline_a_id))

    Conflict.objects.filter(user=user, is_resolved=False).delete()

    active = list(
        Deadline.objects.filter(user=user, is_completed=False, deadline_at__gt=now)
    )

    new_conflicts = []
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]

            if (a.id, b.id) in resolved_pairs:
                continue

            overlap_start = max(a.prep_window_start, b.prep_window_start)
            overlap_end   = min(a.deadline_at,       b.deadline_at)

            if overlap_end <= overlap_start:
                continue

            overlap_hours = (overlap_end - overlap_start).total_seconds() / 3600

            if overlap_hours < 2:
                severity = "mild"
            elif overlap_hours <= 6:
                severity = "moderate"
            else:
                severity = "critical"

            new_conflicts.append(Conflict(
                user=user,
                deadline_a=a,
                deadline_b=b,
                overlap_hours=round(overlap_hours, 2),
                severity=severity,
            ))

    if new_conflicts:
        Conflict.objects.bulk_create(new_conflicts)
        for c in new_conflicts:
            log_event(user, "conflict_detected", metadata={
                "task_a":        c.deadline_a.title,
                "task_b":        c.deadline_b.title,
                "overlap_hours": c.overlap_hours,
                "severity":      c.severity,
            })

    return new_conflicts


# ── Smart plan ───────────────────────────────────────────────────────────────

def compute_smart_plan(user):
    """
    Returns list of (Deadline, score) sorted by score descending.
    Score = 0.40*priority + 0.30*proximity + 0.20*conflict_boost + 0.10*effort
    """
    from .models import Deadline, Conflict

    now = timezone.now()
    PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    active = list(
        Deadline.objects.filter(user=user, is_completed=False, deadline_at__gt=now)
    )

    conflicted_ids = set()
    for c in Conflict.objects.filter(user=user, is_resolved=False):
        conflicted_ids.add(c.deadline_a_id)
        conflicted_ids.add(c.deadline_b_id)

    scored = []
    for d in active:
        hours = max(d.hours_until_deadline, 0.001)

        priority_score  = PRIORITY_WEIGHT.get(d.priority, 2) / 4
        proximity_score = min(1 / hours, 1.0)
        conflict_boost  = 1.0 if d.id in conflicted_ids else 0.0
        effort_score    = min(d.est_hours / 40, 1.0)

        score = (
            priority_score  * 0.40
            + proximity_score * 0.30
            + conflict_boost  * 0.20
            + effort_score    * 0.10
        )
        scored.append((d, round(score, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# ── Reminders ────────────────────────────────────────────────────────────────

def schedule_reminders(user, deadline):
    """
    Create 72h, 24h, and 1h reminders for a deadline.
    Creates one reminder per available channel (email and/or sms).
    Only future remind_at values are created.
    """
    from .models import DeadlineReminder

    now = timezone.now()
    # Wipe old unsent reminders so updates don't create duplicates
    DeadlineReminder.objects.filter(deadline=deadline, is_sent=False).delete()

    # Determine which channels are available for this user
    channels = []
    if user.email:
        channels.append("email")
    try:
        from dashboard.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        if (profile.phone_number or "").strip():
            channels.append("sms")
    except Exception:
        pass
    if not channels:
        channels = ["email"]   # always attempt email as last resort

    for hours_before in [72, 24, 1]:
        remind_at = deadline.deadline_at - timedelta(hours=hours_before)
        if remind_at > now:
            for channel in channels:
                DeadlineReminder.objects.create(
                    user=user,
                    deadline=deadline,
                    remind_at=remind_at,
                    channel=channel,
                )


# ── Analytics ────────────────────────────────────────────────────────────────

def get_analytics_data(user):
    """Returns analytics dict for the analytics template."""
    from .models import Deadline, Conflict
    from collections import defaultdict

    now = timezone.now()

    all_incomplete = list(Deadline.objects.filter(user=user, is_completed=False))
    future = [d for d in all_incomplete if d.deadline_at > now]

    total_tasks       = len(all_incomplete)
    active_conflicts  = Conflict.objects.filter(user=user, is_resolved=False).count()
    total_hours_ahead = round(sum(d.est_hours for d in future), 1)
    overdue_tasks     = len([d for d in all_incomplete if d.deadline_at <= now])
    high_priority     = len([d for d in all_incomplete if d.priority in ("critical", "high")])

    category_dist  = defaultdict(int)
    priority_dist  = defaultdict(int)
    hourly_density = defaultdict(int)
    timeline       = defaultdict(int)

    for d in all_incomplete:
        category_dist[d.type]     += 1
        priority_dist[d.priority] += 1

    for d in future:
        local_dt = localtime(d.deadline_at)
        hourly_density[local_dt.hour]         += 1
        timeline[local_dt.date().isoformat()]  += 1

    effort_data = sorted(
        [(d.title[:40], d.est_hours) for d in future],
        key=lambda x: x[1], reverse=True,
    )[:6]

    return {
        "total_tasks":       total_tasks,
        "active_conflicts":  active_conflicts,
        "total_hours_ahead": total_hours_ahead,
        "overdue_tasks":     overdue_tasks,
        "high_priority":     high_priority,
        "category_dist":     dict(category_dist),
        "priority_dist":     dict(priority_dist),
        "hourly_density":    {str(h): hourly_density.get(h, 0) for h in range(24)},
        "timeline":          dict(sorted(timeline.items())),
        "effort_data":       effort_data,
    }


# ── Calendar data ─────────────────────────────────────────────────────────────

def get_calendar_data(user, year, month):
    """Returns (deadlines_by_date dict, conflict_dates set) for a calendar month."""
    from .models import Deadline, Conflict
    from collections import defaultdict
    import calendar

    first_day = timezone.datetime(year, month, 1, tzinfo=dt_timezone.utc)
    last_day  = timezone.datetime(
        year, month, calendar.monthrange(year, month)[1], 23, 59, 59,
        tzinfo=dt_timezone.utc,
    )

    deadlines = Deadline.objects.filter(
        user=user,
        is_completed=False,
        deadline_at__gte=first_day - timedelta(days=1),
        deadline_at__lte=last_day  + timedelta(days=1),
    )

    conflicted_ids = set()
    for c in Conflict.objects.filter(user=user, is_resolved=False):
        conflicted_ids.add(c.deadline_a_id)
        conflicted_ids.add(c.deadline_b_id)

    deadlines_by_date = defaultdict(list)
    conflict_dates    = set()

    for d in deadlines:
        local_dt = localtime(d.deadline_at)
        if local_dt.year == year and local_dt.month == month:
            date_key = local_dt.date().isoformat()
            deadlines_by_date[date_key].append(d)
            if d.id in conflicted_ids:
                conflict_dates.add(date_key)

    return dict(deadlines_by_date), conflict_dates
