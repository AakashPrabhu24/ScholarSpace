from datetime import timedelta


def app_namespace(request):
    """Injects app_ns to identify the current app namespace for navigation."""
    if request.path.startswith("/manage-work/"):
        return {"app_ns": "manage_work"}
    return {}


def manage_work_stats(request):
    """Injects sidebar stats into every manage_work template."""
    if not request.user.is_authenticated:
        return {}
    if not request.path.startswith("/manage-work/"):
        return {}

    from django.utils import timezone
    from .models import Deadline, Conflict

    now    = timezone.now()
    active = Deadline.objects.filter(user=request.user, is_completed=False)

    return {
        "mw_total_tasks": active.count(),
        "mw_conflicts":   Conflict.objects.filter(
            user=request.user, is_resolved=False
        ).count(),
        "mw_due_72h": active.filter(
            deadline_at__gt=now,
            deadline_at__lte=now + timedelta(hours=72),
        ).count(),
    }
