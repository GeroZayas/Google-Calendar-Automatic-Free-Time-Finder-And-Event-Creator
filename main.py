import PySimpleGUI as sg
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime


# Function to authenticate and create a service object
def authenticate_google():
    flow = InstalledAppFlow.from_client_secrets_file(
        "client_secret_591796920211-6g24f2ol62malqlvsmlvjncb3ah8opps.apps.googleusercontent.com.json",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    creds = flow.run_local_server(port=0)
    service = build("calendar", "v3", credentials=creds)
    return service


# Function to create an event in Google Calendar
def create_event(service, title, start_date, end_date, description):
    event = {
        "summary": title,
        "description": description,
        "start": {"date": start_date, "timeZone": "Europe/Madrid"},
        "end": {"date": end_date, "timeZone": "Europe/Madrid"},
    }
    event = service.events().insert(calendarId="primary", body=event).execute()
    print("Event created: %s" % (event.get("htmlLink")))


# Define the window's contents for PySimpleGUI
layout = [
    [sg.Text("Create an Event in Google Calendar")],
    [sg.Text("Event Title"), sg.InputText(key="title")],
    [sg.Text("Start Date (YYYY-MM-DD)"), sg.InputText(key="start_date")],
    [sg.Text("End Date (YYYY-MM-DD)"), sg.InputText(key="end_date")],
    [sg.Text("Description"), sg.InputText(key="description")],
    [sg.Button("Submit"), sg.Button("Cancel")],
]

# Create the window
window = sg.Window("Event Creator", layout)

# Event loop
while True:
    event, values = window.read()
    if event in (None, "Cancel"):
        break
    elif event == "Submit":
        service = authenticate_google()
        create_event(
            service,
            values["title"],
            values["start_date"],
            values["end_date"],
            values["description"],
        )

window.close()
