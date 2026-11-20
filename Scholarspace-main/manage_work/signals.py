"""
Signals for automatic Google Calendar synchronization.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Deadline, GoogleCalendarSync
from .google_calendar import GoogleCalendarService


@receiver(post_save, sender=Deadline)
def sync_deadline_to_google_calendar(sender, instance, created, **kwargs):
    """Automatically sync deadline to Google Calendar when created or updated."""
    try:
        # Only sync if the deadline is not completed
        if instance.is_completed:
            return
        
        # Check if user has Google Calendar connected
        sync_record = GoogleCalendarSync.objects.filter(user=instance.user).first()
        if not sync_record or not sync_record.is_sync_enabled:
            return
        
        # Sync to Google Calendar
        service = GoogleCalendarService()
        success, message = service.sync_deadline_to_calendar(instance.user, instance)
        
        if success:
            print(f"Successfully synced deadline '{instance.title}' to Google Calendar")
        else:
            print(f"Failed to sync deadline '{instance.title}' to Google Calendar: {message}")
            
    except Exception as e:
        print(f"Error in Google Calendar sync signal: {e}")


@receiver(post_delete, sender=Deadline)
def delete_deadline_from_google_calendar(sender, instance, **kwargs):
    """Remove deadline from Google Calendar when deleted."""
    try:
        # Check if user has Google Calendar connected
        sync_record = GoogleCalendarSync.objects.filter(user=instance.user).first()
        if not sync_record or not sync_record.event_mappings:
            return
        
        # Check if deadline has a Google Calendar event
        deadline_id = str(instance.id)
        if deadline_id in sync_record.event_mappings:
            event_id = sync_record.event_mappings[deadline_id]
            
            # Delete from Google Calendar
            service = GoogleCalendarService()
            credentials = service.get_credentials_from_token(sync_record.token_data)
            
            if credentials:
                success = service.delete_calendar_event(credentials, event_id)
                if success:
                    print(f"Successfully deleted deadline '{instance.title}' from Google Calendar")
                else:
                    print(f"Failed to delete deadline '{instance.title}' from Google Calendar")
            
    except Exception as e:
        print(f"Error in Google Calendar delete signal: {e}")
