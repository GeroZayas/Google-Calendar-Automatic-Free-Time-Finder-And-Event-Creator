import streamlit as st
import datetime
import pytz
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import google.oauth2.credentials
from google.auth.transport.requests import Request


# ===========================================================================
# =====================FUNCTIONS=============================================
# ===========================================================================
# Function to authenticate and create a service object
def authenticate_google():
    creds = None

    # Check if token.json exists and load credentials from it
    if os.path.exists("token.json"):
        try:
            creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
                "token.json", scopes=["https://www.googleapis.com/auth/calendar"]
            )
        except Exception as e:
            st.error(f"Error loading credentials from token.json: {e}")

    # If credentials are missing or invalid, assist the user in obtaining them
    if not creds or not creds.valid:
        st.warning(
            "No valid credentials found. Please ensure you have 'credentials.json'."
        )

        try:
            # Delete the token.json file if it exists (to start fresh)
            if os.path.exists("token.json"):
                os.remove("token.json")

            # Start the OAuth flow to obtain new credentials
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", scopes=["https://www.googleapis.com/auth/calendar"]
            )
            creds = flow.run_local_server(port=0)

            # Save the obtained credentials to token.json for future use
            with open("token.json", "w") as token:
                token.write(creds.to_json())

        except Exception as e:
            st.error(f"Error obtaining credentials: {e}")

    # Return the Google Calendar service object using the obtained credentials
    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception as e:
        st.error(f"Error creating Google Calendar service: {e}")
        return None


def find_free_time(service, date, duration_str):
    # Parse the duration string
    if duration_str == "10 minutes":
        duration = datetime.timedelta(minutes=10)
    elif duration_str == "15 minutes":
        duration = datetime.timedelta(minutes=15)
    elif duration_str == "5 minutes":
        duration = datetime.timedelta(minutes=5)
    elif duration_str == "30 minutes":
        duration = datetime.timedelta(minutes=30)
    elif duration_str == "45 minutes":
        duration = datetime.timedelta(minutes=45)
    elif duration_str == "1 hour":
        duration = datetime.timedelta(hours=1)
    elif duration_str == "1:30 hour":
        duration = datetime.timedelta(minutes=90)
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
    # end_date = start_date + datetime.timedelta(days=1)

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
    event_mapping = {}
    for i, event in enumerate(events, start=1):
        event_id = event["id"]
        start_time = event["start"].get("dateTime", event["start"].get("date"))
        try:
            start_time = datetime.datetime.fromisoformat(start_time).strftime("%H:%M")
        except ValueError:
            start_time = datetime.datetime.fromisoformat(start_time).strftime(
                "%Y-%m-%d"
            )
        formatted_events.append(f"{i}. {start_time} - {event['summary']}")
        event_mapping[i] = event_id

    return formatted_events, event_mapping


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


def modify_event(service, event_id, new_title, new_color_id, new_duration):
    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    event["summary"] = new_title
    event["colorId"] = new_color_id

    # Calculate new end time based on new duration
    start_time = datetime.datetime.fromisoformat(event["start"]["dateTime"])
    if new_duration == "10 minutes":
        end_time = start_time + datetime.timedelta(minutes=10)
    elif new_duration == "15 minutes":
        end_time = start_time + datetime.timedelta(minutes=15)
    elif new_duration == "30 minutes":
        end_time = start_time + datetime.timedelta(minutes=30)
    elif new_duration == "1 hour":
        end_time = start_time + datetime.timedelta(hours=1)
    elif new_duration == "2 hours":
        end_time = start_time + datetime.timedelta(hours=2)

    event["end"]["dateTime"] = end_time.isoformat()

    updated_event = (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=event)
        .execute()
    )
    return updated_event.get("htmlLink")


# ===========================================================================
# =====================APP ELEMENTS AND LAYOUT===============================
# ===========================================================================


# TITLE AND SUBHEADER
# ===========================================================================
st.title("📅 Google Calendar Event Creator")
st.subheader(
    "🌟 Effortlessly schedule your tasks without the hassle — let our app find your free time in Google Calendar! ⏰"
)

# LAYOUT ELEMENTS INPUTS
# ===========================================================================
event_title = st.text_input("📝 Event Title")
event_date = st.date_input("📅 Event Date")
description = st.text_area("📝 Description")
duration = st.selectbox(
    "⏱️ Event Duration",
    [
        "5 minutes",
        "10 minutes",
        "15 minutes",
        "30 minutes",
        "45 minutes",
        "1 hour",
        "1:30 hour",
        "2 hours",
    ],
)
color = st.selectbox(
    "🎨 Event Color",
    [
        "🔵 Blue",
        "💜 Lavender",
        "🟢 Green",
        "🟣 Violet",
        "💖 Pink",
        "💛 Yellow",
        "🟠 Orange",
        "🔹 Highlight Blue",
        "⚪ Grey",
        "🔷 Dark Blue",
        "🟢 Dark Green",
        "🔴 Red",
    ],
)

# BUTTONS, FUNCTIONALITY
# ===========================================================================
if st.button("📅 Show Events"):
    if event_date:
        service = authenticate_google()
        events_list, event_mapping = get_events_for_date(
            service, event_date.strftime("%Y-%m-%d")
        )
        st.write(f"🗓️ Events on {event_date}")
        st.write("\n\n".join(events_list))
        st.session_state.event_mapping = (
            event_mapping  # Store the mapping in session state
        )
    else:
        st.error("❌ Please select a date first")


if st.button("📅 Create Event"):
    if event_date:
        service = authenticate_google()
        if free_time_slots := find_free_time(
            service, event_date.strftime("%Y-%m-%d"), duration
        ):
            start_datetime_str = free_time_slots[0]
            start_datetime = datetime.datetime.fromisoformat(start_datetime_str)
            if duration == "10 minutes":
                end_datetime = start_datetime + datetime.timedelta(minutes=10)
            elif duration == "5 minutes":
                end_datetime = start_datetime + datetime.timedelta(minutes=5)
            elif duration == "15 minutes":
                end_datetime = start_datetime + datetime.timedelta(minutes=15)
            elif duration == "30 minutes":
                end_datetime = start_datetime + datetime.timedelta(minutes=30)
            elif duration == "45 minutes":
                end_datetime = start_datetime + datetime.timedelta(minutes=45)
            elif duration == "1 hour":
                end_datetime = start_datetime + datetime.timedelta(hours=1)
            elif duration == "1:30 hour":
                end_datetime = start_datetime + datetime.timedelta(minutes=90)
            elif duration == "2 hours":
                end_datetime = start_datetime + datetime.timedelta(hours=2)
            end_datetime_str = end_datetime.isoformat()

            color_id = {
                "🔵 Blue": "0",
                "💜 Lavender": "1",
                "🟢 Green": "2",
                "🟣 Violet": "3",
                "💖 Pink": "4",
                "💛 Yellow": "5",
                "🟠 Orange": "6",
                "🔹 Highlight Blue": "7",
                "⚪ Grey": "8",
                "🔷 Dark Blue": "9",
                "🟢 Dark Green": "10",
                "🔴 Red": "11",
            }[color]

            event_link = create_event(
                service,
                event_title,
                start_datetime_str,
                end_datetime_str,
                description,
                color_id=color_id,
            )
            st.success(f"✅ Event created: [Event Link]({event_link})")
        else:
            st.error("❌ No free time slots available on this date")
    else:
        st.error("❌ Please select a date")

# EXTRA OPTIONS, DELETE AND MODIFY
# ===========================================================================
with st.expander("🗑️ Delete Event"):
    event_number_to_delete = st.number_input(
        "🔢 Event Number to Delete", min_value=1, step=1
    )
    if st.button("🗑️ Delete Event"):
        if (
            "event_mapping" in st.session_state
            and event_number_to_delete in st.session_state.event_mapping
        ):
            event_id_to_delete = st.session_state.event_mapping[event_number_to_delete]
            service = authenticate_google()
            delete_event(service, event_id_to_delete)
            st.success(f"✅ Event with ID {event_id_to_delete} deleted successfully")
        else:
            st.error("❌ Invalid event number")

with st.expander("🛠️ Modify Event"):
    event_number_to_modify = st.number_input(
        "🔢 Event Number to Modify", min_value=1, step=1
    )
    new_title = st.text_input("📝 New Event Title")
    new_duration = st.selectbox(
        "⏱️ New Event Duration",
        ["10 minutes", "15 minutes", "30 minutes", "1 hour", "2 hours"],
    )
    new_color = st.selectbox(
        "🎨 New Event Color",
        [
            "🔵 Blue",
            "💜 Lavender",
            "🟢 Green",
            "🟣 Violet",
            "💖 Pink",
            "💛 Yellow",
            "🟠 Orange",
            "🔹 Highlight Blue",
            "⚪ Grey",
            "🔷 Dark Blue",
            "🟢 Dark Green",
            "🔴 Red",
        ],
    )
    if st.button("💾 Modify Event"):
        if (
            "event_mapping" in st.session_state
            and event_number_to_modify in st.session_state.event_mapping
        ):
            event_id_to_modify = st.session_state.event_mapping[event_number_to_modify]
            service = authenticate_google()
            new_color_id = {
                "🔵 Blue": "0",
                "💜 Lavender": "1",
                "🟢 Green": "2",
                "🟣 Violet": "3",
                "💖 Pink": "4",
                "💛 Yellow": "5",
                "🟠 Orange": "6",
                "🔹 Highlight Blue": "7",
                "⚪ Grey": "8",
                "🔷 Dark Blue": "9",
                "🟢 Dark Green": "10",
                "🔴 Red": "11",
            }[new_color]
            event_link = modify_event(
                service, event_id_to_modify, new_title, new_color_id, new_duration
            )
            st.success(f"✅ Event modified: [Event Link]({event_link})")
        else:
            st.error("❌ Invalid event number or missing required fields")

# CLEAR BUTTON
# ===========================================================================
if st.button("Clear"):
    st.experimental_rerun()
