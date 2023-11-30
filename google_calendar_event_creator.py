import PySimpleGUI as sg
import datetime
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import google.oauth2.credentials
from google.auth.transport.requests import Request


# Function to authenticate and create a service object
def authenticate_google():
    creds = None
    # The file token.json stores the user's access and refresh tokens and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists("token.json"):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
            "token.json", scopes=["https://www.googleapis.com/auth/calendar"]
        )

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", scopes=["https://www.googleapis.com/auth/calendar"]
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def find_free_time(service, date, duration_str):
    # Parse the duration string
    if duration_str == "10 minutes":
        duration = datetime.timedelta(minutes=10)
    elif duration_str == "15 minutes":
        duration = datetime.timedelta(minutes=15)
    elif duration_str == "30 minutes":
        duration = datetime.timedelta(minutes=30)
    elif duration_str == "1 hour":
        duration = datetime.timedelta(hours=1)
    elif duration_str == "2 hours":  # New case for 2 hours
        duration = datetime.timedelta(hours=2)

    timezone = pytz.timezone("Europe/Madrid")
    start_date = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone)

    # Get current time with timezone
    current_time = datetime.datetime.now(pytz.timezone("Europe/Madrid"))

    # Check if the start_date is today and before the current time
    if start_date.date() == current_time.date() and start_date < current_time:
        # If it's the same day but the time has already passed, start from the current time
        start_date = current_time

    end_date = start_date + datetime.timedelta(days=1)

    # Define the start and end times for the search window (7 AM to 11 PM)
    search_start_time = start_date.replace(hour=7, minute=0, second=0)
    search_end_time = start_date.replace(hour=23, minute=0, second=0)

    body = {
        "timeMin": search_start_time.isoformat(),
        "timeMax": search_end_time.isoformat(),
        "items": [{"id": "primary"}],
    }

    events_result = service.freebusy().query(body=body).execute()
    busy_times = events_result["calendars"]["primary"]["busy"]

    free_slots = []
    current_time = search_start_time

    for busy_period in busy_times:
        busy_start = datetime.datetime.fromisoformat(busy_period["start"]).astimezone(
            timezone
        )
        while current_time + duration <= busy_start:
            free_slots.append(current_time.isoformat())
            current_time += datetime.timedelta(
                minutes=15
            )  # Check every 15 minutes for a free slot
        current_time = max(
            datetime.datetime.fromisoformat(busy_period["end"]).astimezone(timezone),
            current_time,
        )

        # Add a 10-minute buffer after each busy period
        current_time += datetime.timedelta(minutes=10)

    while current_time + duration <= search_end_time:
        free_slots.append(current_time.isoformat())
        current_time += datetime.timedelta(minutes=15)

    return free_slots


def custom_popup(title, events_list):
    layout = [
        [
            sg.Listbox(
                events_list,
                font=input_font,
                size=(80, 20),
                key="-LIST-",
                select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
            )
        ],
        [sg.Button("Copy to Clipboard"), sg.Button("Close")],
    ]

    window = sg.Window(title, layout)

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, "Close"):
            break
        elif event == "Copy to Clipboard":
            # Check if any event is selected, if not, copy all events
            selected_events = values["-LIST-"] or events_list
            clipboard_content = "\n".join(selected_events)
            sg.clipboard_set(clipboard_content)
            sg.popup(
                "Content copied to clipboard!", auto_close=True, auto_close_duration=1
            )

    window.close()


def get_events_for_date(service, date):
    start_date = datetime.datetime.strptime(date, "%Y-%m-%d").replace(
        tzinfo=pytz.timezone("Europe/Madrid")
    )
    end_date = start_date + datetime.timedelta(days=1)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    formatted_events = []
    for event in events:
        start_time = event["start"].get("dateTime", event["start"].get("date"))
        try:
            # Extract only the time part if it's a dateTime object
            start_time = datetime.datetime.fromisoformat(start_time).strftime("%H:%M")
        except ValueError:
            # Keep the full date if it's a date object (all-day event)
            start_time = datetime.datetime.fromisoformat(start_time).strftime(
                "%Y-%m-%d"
            )
        formatted_events.append(f"{start_time} - {event['summary']}")

    return formatted_events


# Function to create an event in Google Calendar
def create_event(
    service, title, start_datetime, end_datetime, description, color_id="0"
):
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_datetime, "timeZone": "Europe/Madrid"},
        "end": {"dateTime": end_datetime, "timeZone": "Europe/Madrid"},
        "colorId": color_id,  # Set the color of the event
    }

    event = service.events().insert(calendarId="primary", body=event).execute()
    return event.get("htmlLink")


sg.theme("BrightColors")
# sg.theme("Topanga")

# Duration choices
duration_choices = ["10 minutes", "15 minutes", "30 minutes", "1 hour", "2 hours"]

# Font and color configurations
title_font = ("Any", 14, "bold")
label_font = ("Any", 12)
button_font = ("Any", 12, "bold")
input_font = ("Any", 12)
button_color = ("black", "gold")
background_color = "lightgrey"

# Google Calendar color IDs and their descriptions
color_choices = {
    "Blue": "0",
    "Lavender": "1",
    "Green": "2",
    "Violet": "3",
    "Pink": "4",
    "Yellow": "5",
    "Orange": "6",
    "Highlight Blue": "7",
    "Grey": "8",
    "Dark Blue": "9",
    "Dark Green": "10",
    "Red": "11",
}


# Define the layout with style enhancements
layout = [
    [
        sg.Text(
            "Create an Event in Google Calendar",
            font=title_font,
            justification="center",
            pad=(0, 10),
        )
    ],
    [
        sg.Frame(
            layout=[
                [
                    sg.Text("Event Title", font=label_font),
                    sg.InputText(key="title", font=input_font),
                ],
                [
                    sg.Text("Event Date", font=label_font),
                    sg.Input(key="event_date", font=input_font),
                    sg.CalendarButton(
                        "Choose Date",
                        target="event_date",
                        format="%Y-%m-%d",
                        button_color=button_color,
                        font=button_font,
                    ),
                ],
                [
                    sg.Text("Description", font=label_font),
                    sg.InputText(key="description", font=input_font),
                    sg.Button(
                        "Show Events",
                        key="Show_Events",
                        font=button_font,
                        button_color=button_color,
                    ),
                ],
                [
                    sg.Text("Event Duration", font=label_font),
                    sg.Combo(
                        duration_choices,
                        default_value="30 minutes",
                        key="duration",
                        font=input_font,
                    ),
                    sg.Text("Event Color", font=label_font),
                    sg.Combo(
                        list(color_choices.keys()),
                        default_value="Red",
                        font=input_font,
                        key="event_color",
                    ),
                ],
            ],
            title="Event Details",
            font=("Any", 12, "bold"),
            title_color="dark green",
        )
    ],
    [
        sg.Button(
            "Submit",
            font=button_font,
            button_color=button_color,
        ),
        sg.Button("Clear", font=button_font, button_color=button_color),
        sg.Button("Close", font=button_font, button_color="red"),
    ],
]

# Create the window with the layout
window = sg.Window(
    "Google Calendar Event Creator", layout, background_color=background_color
)


# Event loop
while True:
    event, values = window.read()

    if event in (None, "Close"):
        break

    # elif event == "Show_Events":
    #     if values["event_date"]:
    #         service = authenticate_google()
    #         events_list = get_events_for_date(service, values["event_date"])
    #         sg.popup_scrolled(
    #             "Events on " + values["event_date"],
    #             "\n".join(events_list),
    #             font=input_font,
    #             size=(80, 20),
    #         )
    #     else:
    #         sg.popup("Please select a date first")

    elif event == "Show_Events":
        if values["event_date"]:
            service = authenticate_google()
            events_list = get_events_for_date(service, values["event_date"])
            custom_popup("Events on " + values["event_date"], events_list)
        else:
            sg.popup("Please select a date first")

    elif event == "Clear":
        # This will clear all input fields
        for key in values:
            if key in ["title", "event_date", "description"]:
                window[key]("")
    elif event == "Submit":
        if values["event_date"]:
            service = authenticate_google()
            duration = values["duration"]
            if free_time_slots := find_free_time(
                service, values["event_date"], duration
            ):
                # Automatically choose the first available slot
                start_datetime_str = free_time_slots[0]
                start_datetime = datetime.datetime.fromisoformat(start_datetime_str)
                if duration == "10 minutes":
                    end_datetime = start_datetime + datetime.timedelta(minutes=10)
                elif duration == "15 minutes":
                    end_datetime = start_datetime + datetime.timedelta(minutes=15)
                elif duration == "30 minutes":
                    end_datetime = start_datetime + datetime.timedelta(minutes=30)
                elif duration == "1 hour":
                    end_datetime = start_datetime + datetime.timedelta(hours=1)
                elif duration == "2 hours":
                    end_datetime = start_datetime + datetime.timedelta(hours=2)
                end_datetime_str = end_datetime.isoformat()

                selected_color = color_choices[values["event_color"]]
                event_link = create_event(
                    service,
                    values["title"],
                    start_datetime_str,
                    end_datetime_str,
                    values["description"],
                    color_id=selected_color,
                )
                sg.popup(f"Event created: {event_link}")
            else:
                sg.popup("No free time slots available on this date")
        else:
            sg.popup("Please select a date")

    # elif event == "Find Free Time":
    #     if values["event_date"]:
    #         service = authenticate_google()
    #         duration = values["duration"]
    #         free_time_slots = find_free_time(service, values["event_date"], duration)
    #         # Update this part to let the user select from free_time_slots
    #         window["free_time_info"].update(f"Free slots: {free_time_slots}")
    #     else:
    #         sg.popup("Please select a date first")


window.close()
