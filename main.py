import PySimpleGUI as sg
import datetime
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Function to authenticate and create a service object
def authenticate_google():
    flow = InstalledAppFlow.from_client_secrets_file(
        "credentials.json", scopes=["https://www.googleapis.com/auth/calendar"]
    )
    creds = flow.run_local_server(port=0)
    return build("calendar", "v3", credentials=creds)


# Function to find free time slots
def find_free_time(service, date):
    timezone = pytz.timezone("Europe/Madrid")
    start_date = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone)
    end_date = start_date + datetime.timedelta(days=1)

    # Formatting start_date and end_date for the API request
    formatted_start_date = start_date.isoformat()
    formatted_end_date = end_date.isoformat()

    body = {
        "timeMin": formatted_start_date,
        "timeMax": formatted_end_date,
        "items": [{"id": "primary"}],
    }

    events_result = service.freebusy().query(body=body).execute()
    busy_times = events_result["calendars"]["primary"]["busy"]

    free_slots = []
    current_time = start_date

    for busy_period in busy_times:
        busy_start = datetime.datetime.fromisoformat(busy_period["start"]).astimezone(
            timezone
        )
        while current_time < busy_start:
            free_slots.append(current_time.isoformat())
            current_time += datetime.timedelta(hours=1)
        busy_end = datetime.datetime.fromisoformat(busy_period["end"]).astimezone(
            timezone
        )
        current_time = busy_end

    # Check for free time after the last busy period
    while current_time < end_date:
        free_slots.append(current_time.isoformat())
        current_time += datetime.timedelta(hours=1)

    return free_slots


# Function to create an event in Google Calendar
def create_event(service, title, start_datetime, end_datetime, description):
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_datetime, "timeZone": "Europe/Madrid"},
        "end": {"dateTime": end_datetime, "timeZone": "Europe/Madrid"},
    }
    event = service.events().insert(calendarId="primary", body=event).execute()
    return event.get("htmlLink")


# Duration choices
duration_choices = ["15 minutes", "30 minutes", "1 hour"]

# Define the window's contents for PySimpleGUI
layout = [
    [sg.Text("Create an Event in Google Calendar")],
    [sg.Text("Event Title"), sg.InputText(key="title")],
    [
        sg.Text("Event Date"),
        sg.Input(key="event_date"),
        sg.CalendarButton("Choose Date", target="event_date", format="%Y-%m-%d"),
    ],
    [sg.Text("Description"), sg.InputText(key="description")],
    [
        sg.Text("Event Duration"),
        sg.Combo(duration_choices, default_value="30 minutes", key="duration"),
    ],
    [sg.Button("Find Free Time"), sg.Button("Submit"), sg.Button("Cancel")],
    [sg.Text("", size=(40, 1), key="free_time_info")],
]

# Create the window
window = sg.Window("Event Creator", layout)

# Event loop
while True:
    event, values = window.read()

    if event in (None, "Cancel"):
        break
    elif event == "Submit":
        # Here, you should include logic to select a specific free time slot
        # For now, it will require manual entry or modification
        service = authenticate_google()
        event_link = create_event(
            service,
            values["title"],
            values["event_date"] + "T09:00:00",
            values["event_date"] + "T10:00:00",
            values["description"],
        )
        sg.popup(f"Event created: {event_link}")
    elif event == "Find Free Time":
        if values["event_date"]:
            service = authenticate_google()
            free_time_slots = find_free_time(service, values["event_date"])
            # You can update this part to let the user select from free_time_slots
            window["free_time_info"].update(f"Free slots: {free_time_slots}")
        else:
            sg.popup("Please select a date first")

window.close()
