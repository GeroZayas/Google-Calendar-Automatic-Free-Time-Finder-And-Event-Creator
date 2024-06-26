import streamlit as st
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
    if os.path.exists("token.json"):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
            "token.json", scopes=["https://www.googleapis.com/auth/calendar"]
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Delete the token.json file if it exists
            if os.path.exists("token.json"):
                os.remove("token.json")

            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", scopes=["https://www.googleapis.com/auth/calendar"]
            )
            creds = flow.run_local_server(port=0)

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
    elif duration_str == "2 hours":
        duration = datetime.timedelta(hours=2)

    timezone = pytz.timezone("Europe/Madrid")
    start_date = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone)

    # Get current time with timezone
    current_time = datetime.datetime.now(pytz.timezone("Europe/Madrid"))

    # Define the start and end times for the search window (7 AM to 11 PM)
    search_start_time = start_date.replace(hour=7, minute=0, second=0, microsecond=0)
    search_end_time = start_date.replace(hour=23, minute=0, second=0, microsecond=0)

    # If the start_date is today and it's already past the search window start time, update search_start_time to the current time
    if start_date.date() == current_time.date() and search_start_time < current_time:
        search_start_time = current_time
    end_date = start_date + datetime.timedelta(days=1)

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
        event_id = event["id"]
        start_time = event["start"].get("dateTime", event["start"].get("date"))
        try:
            start_time = datetime.datetime.fromisoformat(start_time).strftime("%H:%M")
        except ValueError:
            start_time = datetime.datetime.fromisoformat(start_time).strftime(
                "%Y-%m-%d"
            )
        formatted_events.append(f"ID: {event_id} | {start_time} - {event['summary']}")

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


def delete_event(service, event_id):
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def modify_event(
    service,
    event_id,
    new_title,
    new_description,
    new_start_datetime,
    new_end_datetime,
    new_color_id="0",
):
    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    event["summary"] = new_title
    event["description"] = new_description
    event["start"] = {"dateTime": new_start_datetime, "timeZone": "Europe/Madrid"}
    event["end"] = {"dateTime": new_end_datetime, "timeZone": "Europe/Madrid"}
    event["colorId"] = new_color_id

    updated_event = (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=event)
        .execute()
    )
    return updated_event.get("htmlLink")


st.title("Google Calendar Event Creator")

event_title = st.text_input("Event Title")
event_date = st.date_input("Event Date")
description = st.text_area("Description")
duration = st.selectbox(
    "Event Duration", ["10 minutes", "15 minutes", "30 minutes", "1 hour", "2 hours"]
)
color = st.selectbox(
    "Event Color",
    [
        "Blue",
        "Lavender",
        "Green",
        "Violet",
        "Pink",
        "Yellow",
        "Orange",
        "Highlight Blue",
        "Grey",
        "Dark Blue",
        "Dark Green",
        "Red",
    ],
)

if st.button("Show Events"):
    if event_date:
        service = authenticate_google()
        events_list = get_events_for_date(service, event_date.strftime("%Y-%m-%d"))
        st.write(f"Events on {event_date}")
        st.write("\n\n".join(events_list))
    else:
        st.error("Please select a date first")

if st.button("Create Event"):
    if event_date:
        service = authenticate_google()
        if free_time_slots := find_free_time(
            service, event_date.strftime("%Y-%m-%d"), duration
        ):
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

            color_id = {
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
            }[color]

            event_link = create_event(
                service,
                event_title,
                start_datetime_str,
                end_datetime_str,
                description,
                color_id=color_id,
            )
            st.success(f"Event created: [Event Link]({event_link})")
        else:
            st.error("No free time slots available on this date")
    else:
        st.error("Please select a date")

with st.expander("Delete Event"):
    event_id_to_delete = st.text_input("Event ID to Delete")
    if st.button("Delete Event"):
        if event_id_to_delete:
            service = authenticate_google()
            delete_event(service, event_id_to_delete)
            st.success(f"Event with ID {event_id_to_delete} deleted successfully")
        else:
            st.error("Please enter an event ID to delete")

with st.expander("Modify Event"):
    event_id_to_modify = st.text_input("Event ID to Modify")
    new_title = st.text_input("New Event Title")
    new_description = st.text_area("New Description")
    new_start_datetime = st.text_input("New Start Datetime (YYYY-MM-DDTHH:MM:SS)")
    new_end_datetime = st.text_input("New End Datetime (YYYY-MM-DDTHH:MM:SS)")
    new_color = st.selectbox(
        "New Event Color",
        [
            "Blue",
            "Lavender",
            "Green",
            "Violet",
            "Pink",
            "Yellow",
            "Orange",
            "Highlight Blue",
            "Grey",
            "Dark Blue",
            "Dark Green",
            "Red",
        ],
    )
    if st.button("Modify Event"):
        if event_id_to_modify and new_start_datetime and new_end_datetime:
            service = authenticate_google()
            new_color_id = {
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
            }[new_color]
            event_link = modify_event(
                service,
                event_id_to_modify,
                new_title,
                new_description,
                new_start_datetime,
                new_end_datetime,
                new_color_id,
            )
            st.success(f"Event modified: [Event Link]({event_link})")
        else:
            st.error("Please enter all required fields to modify the event")

if st.button("Clear"):
    st.experimental_rerun()
