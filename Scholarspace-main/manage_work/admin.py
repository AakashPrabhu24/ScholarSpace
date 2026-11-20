from django.contrib import admin
from .models import Deadline, Conflict, DeadlineReminder, TelemetryEvent


@admin.register(Deadline)
class DeadlineAdmin(admin.ModelAdmin):
    list_display  = ("title", "user", "type", "priority", "deadline_at", "est_hours", "is_completed")
    list_filter   = ("type", "priority", "is_completed")
    search_fields = ("title", "user__username")
    ordering      = ("deadline_at",)


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    list_display  = ("deadline_a", "deadline_b", "overlap_hours", "severity", "is_resolved", "detected_at")
    list_filter   = ("severity", "is_resolved")
    ordering      = ("-detected_at",)


@admin.register(DeadlineReminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display  = ("deadline", "user", "remind_at", "channel", "is_sent", "sent_at")
    list_filter   = ("is_sent", "channel")
    ordering      = ("remind_at",)


@admin.register(TelemetryEvent)
class TelemetryAdmin(admin.ModelAdmin):
    list_display  = ("user", "event_type", "deadline", "occurred_at")
    list_filter   = ("event_type",)
    search_fields = ("user__username",)
    ordering      = ("-occurred_at",)
