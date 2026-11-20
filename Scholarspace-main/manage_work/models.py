from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import json


class Deadline(models.Model):
    TYPE_CHOICES = [
        ("assignment", _("Assignment")),
        ("exam",       _("Exam")),
        ("hackathon",  _("Hackathon")),
        ("project",    _("Project")),
    ]
    PRIORITY_CHOICES = [
        ("critical", _("Critical")),
        ("high",     _("High")),
        ("medium",   _("Medium")),
        ("low",      _("Low")),
    ]

    user         = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="deadlines"
    )
    title        = models.CharField(max_length=200)
    type         = models.CharField(max_length=20, choices=TYPE_CHOICES, default="assignment")
    priority     = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    deadline_at  = models.DateTimeField()
    est_hours    = models.FloatField(default=1.0)
    notes        = models.TextField(blank=True, default="")
    is_completed = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deadline_at"]

    def __str__(self):
        return f"{self.title} ({self.user.username})"

    @property
    def is_overdue(self):
        return not self.is_completed and self.deadline_at < timezone.now()

    @property
    def prep_window_start(self):
        return self.deadline_at - timedelta(hours=self.est_hours)

    @property
    def hours_until_deadline(self):
        delta = self.deadline_at - timezone.now()
        return max(delta.total_seconds() / 3600, 0)

    @property
    def is_due_within_72h(self):
        return 0 < self.hours_until_deadline <= 72


class Conflict(models.Model):
    SEVERITY_CHOICES = [
        ("mild",     _("Mild")),
        ("moderate", _("Moderate")),
        ("critical", _("Critical")),
    ]

    user          = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conflicts"
    )
    deadline_a    = models.ForeignKey(
        Deadline, on_delete=models.CASCADE, related_name="conflicts_as_a"
    )
    deadline_b    = models.ForeignKey(
        Deadline, on_delete=models.CASCADE, related_name="conflicts_as_b"
    )
    overlap_hours = models.FloatField()
    severity      = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    is_resolved   = models.BooleanField(default=False)
    detected_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("deadline_a", "deadline_b")

    def __str__(self):
        return (
            f"Conflict: {self.deadline_a.title} vs {self.deadline_b.title} "
            f"({self.severity}, {self.overlap_hours}h)"
        )


class DeadlineReminder(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms",   "SMS"),
    ]

    user      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reminders")
    deadline  = models.ForeignKey(
        Deadline, on_delete=models.CASCADE, related_name="reminders"
    )
    remind_at = models.DateTimeField()
    channel   = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="email")
    is_sent   = models.BooleanField(default=False)
    sent_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["remind_at"]

    def __str__(self):
        return f"Reminder for '{self.deadline.title}' at {self.remind_at:%d %b %H:%M}"


class TelemetryEvent(models.Model):
    EVENT_CHOICES = [
        ("deadline_created",   "Deadline Created"),
        ("deadline_updated",   "Deadline Updated"),
        ("deadline_completed", "Deadline Completed"),
        ("deadline_deleted",   "Deadline Deleted"),
        ("conflict_detected",  "Conflict Detected"),
        ("conflict_resolved",  "Conflict Resolved"),
        ("reminder_sent",      "Reminder Sent"),
        ("smart_plan_viewed",  "Smart Plan Viewed"),
        ("analytics_viewed",   "Analytics Viewed"),
    ]

    user       = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="telemetry_events"
    )
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    deadline   = models.ForeignKey(
        Deadline, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="telemetry_events"
    )
    metadata    = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.event_type} — {self.user.username} @ {self.occurred_at:%Y-%m-%d %H:%M}"


class GoogleCalendarSync(models.Model):
    """Store Google Calendar OAuth tokens and event mappings for users."""
    
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="google_calendar_sync"
    )
    token_data = models.JSONField(default=dict)  # Store OAuth tokens
    event_mappings = models.JSONField(default=dict)  # Map deadline_id -> calendar_event_id
    is_sync_enabled = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.user.username} - Google Calendar Sync"
