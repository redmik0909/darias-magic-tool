import os
import json
import tempfile
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from crypto_utils import decrypt_credentials, is_setup_done

SCOPES     = ["https://www.googleapis.com/auth/calendar.readonly"]
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
APP_DATA   = os.path.join(os.environ.get("APPDATA", BASE_DIR), "DariasMagicTool")
os.makedirs(APP_DATA, exist_ok=True)
TOKEN_FILE = os.path.join(APP_DATA, "token.json")


def get_service():
    """Authenticate and return Google Calendar service."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Decrypt credentials to a temp file
            creds_data = decrypt_credentials()
            if not creds_data:
                raise Exception("Credentials non disponibles. Contactez l'administrateur.")

            # Write decrypted creds to temp file
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="wb")
            tmp.write(creds_data)
            tmp.close()

            try:
                flow  = InstalledAppFlow.from_client_secrets_file(tmp.name, SCOPES)
                creds = flow.run_local_server(port=0)
            finally:
                os.unlink(tmp.name)  # Delete temp file immediately

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_calendars():
    """Return list of all calendars."""
    service = get_service()
    result  = service.calendarList().list().execute()
    return result.get("items", [])


def get_events_for_month(calendar_id, year, month):
    """Get all events for a calendar in a given month. Returns {date_str: [events]}"""
    import calendar as cal_module
    service   = get_service()
    first_day = datetime(year, month, 1)
    last_day  = datetime(year, month, cal_module.monthrange(year, month)[1], 23, 59, 59)

    result = service.events().list(
        calendarId=calendar_id,
        timeMin=first_day.isoformat() + "Z",
        timeMax=last_day.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime",
        maxResults=500
    ).execute()

    events_by_date = {}
    for event in result.get("items", []):
        start   = event.get("start", {})
        dt_str  = start.get("dateTime", start.get("date", ""))
        if dt_str:
            date_key = dt_str[:10]
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append({
                "id":          event.get("id", ""),
                "summary":     event.get("summary", "Sans titre"),
                "description": event.get("description", ""),
                "location":    event.get("location", ""),
                "start":       dt_str,
                "end":         event.get("end", {}).get("dateTime", ""),
            })
    return events_by_date


def get_events_for_day(calendar_id, date_str):
    """Get events for a specific date. Returns list of events."""
    service   = get_service()
    day_start = datetime.strptime(date_str, "%Y-%m-%d")
    day_end   = day_start + timedelta(days=1)

    result = service.events().list(
        calendarId=calendar_id,
        timeMin=day_start.isoformat() + "Z",
        timeMax=day_end.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = []
    for event in result.get("items", []):
        start = event.get("start", {})
        end   = event.get("end", {})
        events.append({
            "id":          event.get("id", ""),
            "summary":     event.get("summary", "Sans titre"),
            "description": event.get("description", ""),
            "location":    event.get("location", ""),
            "start":       start.get("dateTime", start.get("date", "")),
            "end":         end.get("dateTime", end.get("date", "")),
        })
    return events


def find_calendar_by_name(keyword):
    """Find calendar by keyword. Returns (id, name) or (None, None)."""
    for cal in get_calendars():
        if keyword.lower() in cal.get("summary", "").lower():
            return cal["id"], cal["summary"]
    return None, None


def format_time(dt_str):
    """Format ISO datetime to HHhMM."""
    if not dt_str or len(dt_str) < 16:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Hh%M")
    except Exception:
        return dt_str[11:16]