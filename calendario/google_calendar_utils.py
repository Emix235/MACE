# google_calendar_utils.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.conf import settings
from datetime import datetime, timedelta


def get_google_auth_flow(request):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://accounts.google.com/o/oauth2/token",
            }
        },
        scopes=settings.GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_OAUTH2_REDIRECT_URI,
    )
    return flow


def save_google_tokens(user_model, user_id, tokens):
    user = user_model.objects.get(id=user_id)
    user.google_access_token = tokens['access_token']
    user.google_refresh_token = tokens.get('refresh_token', user.google_refresh_token)
    user.google_token_expiry = datetime.now() + timedelta(seconds=tokens['expires_in'])
    user.google_calendar_enabled = True
    user.save()


# google_calendar_utils.py
def create_google_calendar_event(user_model, user_id, event_data):
    user = user_model.objects.get(id=user_id)
    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
    )

    service = build('calendar', 'v3', credentials=credentials)
    event = service.events().insert(calendarId='primary', body=event_data).execute()
    return event
