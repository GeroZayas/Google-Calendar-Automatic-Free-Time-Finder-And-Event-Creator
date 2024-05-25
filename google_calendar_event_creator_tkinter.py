import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import datetime
import pytz
from google.auth.transport.requests import Request
from google.oauth2 import credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

# Function to authenticate and create a service object
def authenticate_google():
    creds = None
    if os.path.exists("token.json"):
        creds = credentials.Credentials.from_authorized_user_file(
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
    elif duration_str == "2 hours":  # New case for 2 hours
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


def custom_popup(title, events_list):
    popup_window = tk.Toplevel()
    popup_window.title(title)

    listbox = tk.Listbox(popup_window, selectmode=tk.EXTENDED)
    for event in events_list:
        listbox.insert(tk.END, event)
    listbox.pack()

    def copy_to_clipboard():
        selected_events = listbox.curselection()
        if selected_events:
            clipboard_content = "\n".join([events_list[i] for i in selected_events])
        else:
            clipboard_content = "\n".join(events_list)
        popup_window.clipboard_clear()
        popup_window.clipboard_append(clipboard_content)
        popup_window.update()
        messagebox.showinfo("Copy to Clipboard", "Content copied to clipboard!")

    def download_to_file():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text Files", "*.txt")]
        )
        if file_path:
            with open(file_path, "w") as file:
                file.write("\n".join(events_list))
            messagebox.showinfo("Download to File", "Events saved to file!")

    copy_button = tk.Button(popup_window, text="Copy to Clipboard", command=copy_to_clipboard)
    copy_button.pack()

    download_button = tk.Button(popup_window, text="Download to File", command=download_to_file)
    download_button.pack()

    close_button = tk.Button(popup_window, text="Close", command=popup_window.destroy)
    close_button.pack()


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


# Main Tkinter window
root = tk.Tk()
root.title("Google Calendar Event Creator")

# Rest of the code for the Tkinter GUI layout and event handling will go here

root.mainloop()
