from django.urls import path
from . import views

app_name = "manage_work"

urlpatterns = [
    path("",                             views.dashboard_view,        name="dashboard"),
    path("add/",                         views.add_deadline_view,     name="add_deadline"),
    path("tasks/",                       views.my_tasks_view,         name="my_tasks"),
    path("calendar/",                    views.calendar_view,         name="calendar"),
    path("conflicts/",                   views.conflicts_view,        name="conflicts"),
    path("conflicts/<int:pk>/resolve/",  views.resolve_conflict_view, name="resolve_conflict"),
    path("smart-plan/",                  views.smart_plan_view,       name="smart_plan"),
    path("reminders/",                   views.reminders_view,        name="reminders"),
    path("analytics/",                   views.analytics_view,        name="analytics"),
    path("deadlines/<int:pk>/complete/", views.complete_deadline_view, name="complete_deadline"),
    path("deadlines/<int:pk>/delete/",   views.delete_deadline_view,  name="delete_deadline"),
    path("load-sample/",                 views.load_sample_view,      name="load_sample"),
    path("clear-all/",                   views.clear_all_view,        name="clear_all"),
    path("telemetry/",                   views.telemetry_view,        name="telemetry"),
    path("sms-settings/",               views.sms_settings_view,     name="sms_settings"),
    path("sync-google-calendar/",        views.sync_google_calendar_view, name="sync_google_calendar"),
    path("google-calendar-connect/",     views.google_calendar_connect_view, name="google_calendar_connect"),
    path("google-calendar-callback/",    views.google_calendar_callback_view, name="google_calendar_callback"),
    path("google-calendar-disconnect/",  views.google_calendar_disconnect_view, name="google_calendar_disconnect"),
]
