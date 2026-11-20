"""
Google Calendar API integration for automatic deadline synchronization.
"""
import os
import json
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import google.auth

class GoogleCalendarService:
    """Service for integrating with Google Calendar API."""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    REDIRECT_URI = 'http://127.0.0.1:8000/manage-work/google-calendar-callback/'
    
    def __init__(self):
        self.client_config = {
            "web": {
                "client_id": getattr(settings, 'GOOGLE_CLIENT_ID', ''),
                "client_secret": getattr(settings, 'GOOGLE_CLIENT_SECRET', ''),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.REDIRECT_URI]
            }
        }
    
    def get_authorization_url(self, user):
        """Generate OAuth2 authorization URL for Google Calendar access."""
        try:
            flow = Flow.from_client_config(
                self.client_config,
                scopes=self.SCOPES,
                redirect_uri=self.REDIRECT_URI
            )
            
            # Store state in session for security
            state = f"google_calendar_{user.id}_{timezone.now().timestamp()}"
            flow.state = state
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            return authorization_url, state
            
        except Exception as e:
            print(f"Error generating authorization URL: {e}")
            return None, None
    
    def get_credentials_from_token(self, token_data):
        """Create credentials object from token data."""
        try:
            credentials = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=self.client_config['web']['token_uri'],
                client_id=self.client_config['web']['client_id'],
                client_secret=self.client_config['web']['client_secret'],
                scopes=self.SCOPES
            )
            
            # Refresh token if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                
            return credentials
            
        except Exception as e:
            print(f"Error creating credentials: {e}")
            return None
    
    def create_calendar_event(self, credentials, deadline):
        """Create a Google Calendar event for a deadline."""
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            # Format event data
            event = {
                'summary': deadline.title,
                'description': f"Priority: {deadline.get_priority_display()}\n"
                              f"Type: {deadline.get_type_display()}\n"
                              f"Estimated Hours: {deadline.est_hours}h\n"
                              f"Notes: {deadline.notes}",
                'start': {
                    'dateTime': deadline.deadline_at.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': (deadline.deadline_at + timedelta(hours=1)).isoformat(),
                    'timeZone': 'UTC',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},       # 1 hour before
                    ],
                },
                'colorId': self._get_color_id(deadline.priority),
            }
            
            # Insert event into primary calendar
            event = service.events().insert(calendarId='primary', body=event).execute()
            
            return event.get('id')
            
        except Exception as e:
            print(f"Error creating calendar event: {e}")
            return None
    
    def update_calendar_event(self, credentials, deadline, event_id):
        """Update an existing Google Calendar event."""
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            event = {
                'summary': deadline.title,
                'description': f"Priority: {deadline.get_priority_display()}\n"
                              f"Type: {deadline.get_type_display()}\n"
                              f"Estimated Hours: {deadline.est_hours}h\n"
                              f"Notes: {deadline.notes}",
                'start': {
                    'dateTime': deadline.deadline_at.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': (deadline.deadline_at + timedelta(hours=1)).isoformat(),
                    'timeZone': 'UTC',
                },
                'colorId': self._get_color_id(deadline.priority),
            }
            
            event = service.events().update(
                calendarId='primary', 
                eventId=event_id, 
                body=event
            ).execute()
            
            return event.get('id')
            
        except Exception as e:
            print(f"Error updating calendar event: {e}")
            return None
    
    def delete_calendar_event(self, credentials, event_id):
        """Delete a Google Calendar event."""
        try:
            service = build('calendar', 'v3', credentials=credentials)
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
            
        except Exception as e:
            print(f"Error deleting calendar event: {e}")
            return False
    
    def sync_deadline_to_calendar(self, user, deadline):
        """Sync a single deadline to Google Calendar."""
        try:
            from .models import GoogleCalendarSync
            
            # Get user's Google credentials
            sync_record = GoogleCalendarSync.objects.filter(user=user).first()
            if not sync_record:
                return False, "Google Calendar not connected"
            
            credentials = self.get_credentials_from_token(sync_record.token_data)
            if not credentials:
                return False, "Invalid credentials"
            
            # Create or update event
            if sync_record.event_mappings and str(deadline.id) in sync_record.event_mappings:
                # Update existing event
                event_id = sync_record.event_mappings[str(deadline.id)]
                new_event_id = self.update_calendar_event(credentials, deadline, event_id)
                if new_event_id:
                    return True, "Event updated"
            else:
                # Create new event
                event_id = self.create_calendar_event(credentials, deadline)
                if event_id:
                    # Update sync record
                    if not sync_record.event_mappings:
                        sync_record.event_mappings = {}
                    sync_record.event_mappings[str(deadline.id)] = event_id
                    sync_record.save()
                    return True, "Event created"
            
            return False, "Failed to sync event"
            
        except Exception as e:
            print(f"Error syncing deadline: {e}")
            return False, f"Error: {str(e)}"
    
    def _get_color_id(self, priority):
        """Get Google Calendar color ID based on deadline priority."""
        color_map = {
            'critical': '11',  # Red
            'high': '10',      # Orange
            'medium': '5',     # Yellow
            'low': '2',        # Green
        }
        return color_map.get(priority, '1')  # Default to blue
