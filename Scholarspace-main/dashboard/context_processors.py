def manage_work(request):
    """Injects manage_work_url so the navbar Manage Work link always appears."""
    try:
        from django.urls import reverse
        return {"manage_work_url": reverse("manage_work:dashboard")}
    except Exception:
        return {"manage_work_url": "/manage-work/"}


def notification_stats(request):
    """Injects unread notification count into every template."""
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    try:
        from .models import Notification
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return {"unread_notification_count": count}
    except Exception:
        return {"unread_notification_count": 0}
