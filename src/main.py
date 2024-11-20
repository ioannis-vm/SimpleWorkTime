import os
import argparse
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import time
from datetime import datetime, timedelta

# Scope for access to the calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']

def load_credentials(credentials_file, token_file):
    def new_creds():
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        creds = flow.run_local_server(port=0)
        return creds

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                creds = new_creds()
        else:
            creds = new_creds()
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    return creds


def create_calendar_event(
    service, calendar_id, start_time, end_time, summary='Work session'
):
    if (end_time - start_time).seconds < 10:
        print('Event too short, skipping.')
        return

    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'America/Los_Angeles',
        },
        'colorId': '7',
    }
    event = service.events().insert(calendarId=calendar_id, body=event).execute()
    print(f'Event created: {event.get("htmlLink")}')


def get_config_path():
    home_dir = os.path.expanduser('~')
    config_dir = os.path.join(home_dir, '.config', 'CalTrack')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    return config_dir


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'description',
        type=str,
        help="Event description.",
    )
    args = parser.parse_args()

    if args.description:
        event_name = args.description
    else:
        event_name = input("Enter the name of the event: ")

    print("Current time:", datetime.now().strftime("%H:%M:%S"))
    print(
        "Press Enter to start working and to pause/resume. Type 'exit' and press Enter to quit."
    )

    total_time = 0.0
    working = False
    start_time = None

    config_path = get_config_path()
    credentials_file = os.path.join(config_path, 'credentials.json')
    token_file = os.path.join(config_path, 'token.json')
    config_file = os.path.join(config_path, 'config.json')

    with open(config_file, 'r') as file:
        config = json.load(file)
    calendar_id = config.get('calendar_id')
    creds = load_credentials(credentials_file, token_file)
    service = build('calendar', 'v3', credentials=creds)

    while True:
        try:
            user_input = input()
            if user_input.lower() == 'exit':
                if working:
                    end_time = datetime.now()
                    total_time += (end_time - start_time).total_seconds()
                    create_calendar_event(
                        service,
                        calendar_id,
                        start_time,
                        end_time,
                        summary=event_name,
                    )
                break
        except (EOFError, KeyboardInterrupt):
            print("\nCtrl-D detected, exiting...")
            if working:
                end_time = datetime.now()
                total_time += (end_time - start_time).total_seconds()
                create_calendar_event(
                    service, calendar_id, start_time, end_time, summary=event_name
                )
            break

        if working:
            end_time = datetime.now()
            total_time += (end_time - start_time).total_seconds()
            create_calendar_event(
                service, calendar_id, start_time, end_time, summary=event_name
            )
            working = False
            print("Work paused. Press Enter to resume.")
        else:
            start_time = datetime.now()
            working = True
            print("Working... Press Enter to pause.")

    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(
        f"Total work time in this session: "
        f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    )


if __name__ == '__main__':
    main()



def rename_events(service, calendar_id, start_date, end_date, old_name, new_name):
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime',
        )
        .execute()
    )
    events = events_result.get('items', [])

    for event in events:
        if event.get('summary') == old_name:
            event['summary'] = new_name
            updated_event = service.events().update(calendarId=calendar_id, eventId=event['id'], body=event).execute()
            print(f'Updated event: {updated_event.get("htmlLink")}')


    # # Example usage:
    # # Define your time window
    # import pytz
    # start_date = datetime.now(pytz.timezone('America/Los_Angeles')) - timedelta(days=2)
    # end_date = datetime.now(pytz.timezone('America/Los_Angeles'))

    # # Define the old and new names
    # old_name = "PhD Research: Meeting recollection"
    # new_name = "RID Project: RC Frames"

    # # Call the function
    # rename_events(service, calendar_id, start_date, end_date, old_name, new_name)
