import re
import os
import argparse
import json
import tzlocal
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import time
from datetime import datetime, timedelta
import tempfile
import subprocess


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
    service, calendar_id, start_time, end_time, summary='Work session', color_id='7'
):
    if (end_time - start_time).seconds < 10:
        print('Event too short, skipping.')
        return

    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': tzlocal.get_localzone().key,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': tzlocal.get_localzone().key,
        },
        'colorId': color_id,
    }
    event = service.events().insert(calendarId=calendar_id, body=event).execute()
    print(f'Event created: {event.get("htmlLink")}')


def get_config_path():
    home_dir = os.path.expanduser('~')
    config_dir = os.path.join(home_dir, '.config', 'CalTrack')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    return config_dir


def add_text(service, calendar_id):
    """
    Opens a text editor to input a log entry, parses it, and creates calendar events.

    Parameters
    ----------
    service : googleapiclient.discovery.Resource
        The authenticated Google Calendar service.
    calendar_id : str
        The ID of the Google Calendar to add events to.
    """
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
        temp_file_path = temp_file.name

    # Open the text editor
    editor = os.getenv(
        'EDITOR', 'nano'
    )  # Use $EDITOR environment variable or default to 'nano'
    try:
        subprocess.call(f'{editor} {temp_file_path}', shell=True)
    except Exception as e:
        print(f'Error opening editor: {e}')
        os.remove(temp_file_path)
        return

    # Read the text from the file
    try:
        with open(temp_file_path, 'r') as temp_file:
            text = temp_file.read()
    except Exception as e:
        print(f'Error reading temporary file: {e}')
        os.remove(temp_file_path)
        return

    # Delete the temporary file
    os.remove(temp_file_path)

    # Parse the log entry
    try:
        parsed_log = parse_org_log(text)
        task_name = parsed_log['task_name']
        clock_events = parsed_log['clock_events']
    except Exception as e:
        print(f'Error parsing log entry: {e}')
        return

    # Create calendar events
    for event in clock_events:
        create_calendar_event(
            service, calendar_id, event['start'], event['end'], summary=task_name
        )
    print(f'Events created successfully for task: {task_name}')


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
            updated_event = (
                service.events()
                .update(calendarId=calendar_id, eventId=event['id'], body=event)
                .execute()
            )
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


def parse_org_log(log_entry):
    """
    Parses an Org task entry with CLOCK events.

    Parameters
    ----------
    log_entry : str
        The log entry to parse.

    Returns
    -------
    dict
        A dictionary containing the task name and a list of CLOCK events
        with their start and end times as datetime objects.
    """
    # Match the task name after one or more asterisks
    task_name_match = re.search(r'^\*+\s+(.*)', log_entry, re.MULTILINE)
    if not task_name_match:
        raise ValueError('Task name not found in log entry.')
    task_name = task_name_match.group(1).strip()

    # Match each CLOCK line and extract the start and end timestamps
    clock_pattern = re.compile(r'CLOCK: \[(.*?)\]--\[(.*?)\]')
    clock_matches = clock_pattern.findall(log_entry)

    # Parse the timestamps into datetime objects
    clock_events = []
    for start, end in clock_matches:
        start_dt = datetime.strptime(start, '%Y-%m-%d %a %H:%M')
        end_dt = datetime.strptime(end, '%Y-%m-%d %a %H:%M')
        clock_events.append({'start': start_dt, 'end': end_dt})

    return {'task_name': task_name, 'clock_events': clock_events}


def create_events_from_log(log_entry, service, calendar_id):
    """
    Parses a log entry and creates calendar events for each CLOCK entry.

    Parameters
    ----------
    log_entry : str
        The log entry containing task name and CLOCK events.
    service : googleapiclient.discovery.Resource
        The authenticated Google Calendar service.
    calendar_id : str
        The ID of the Google Calendar to add events to.
    """
    # Parse the log entry
    parsed_log = parse_org_log(log_entry)
    task_name = parsed_log['task_name']
    clock_events = parsed_log['clock_events']

    # Create events in Google Calendar
    for event in clock_events:
        create_calendar_event(
            service, calendar_id, event['start'], event['end'], summary=task_name
        )


def create_default_sleep_events(service, calendar_id):
    """
    Adds default Sleep events.

    Creates two sleep events, one for the night before and one for the
    morning of the current day, split at 12:00AM.

    Parameters
    ----------
    service : googleapiclient.discovery.Resource
        The authenticated Google Calendar service.
    calendar_id : str
        The ID of the Google Calendar to add events to.
    """
    now = datetime.now()
    create_calendar_event(
        service,
        calendar_id,
        datetime(now.year, now.month, now.day, 0, 0, 0),
        datetime(now.year, now.month, now.day, 4, 0, 0),
        summary='Sleep',
        color_id=None,
    )
    create_calendar_event(
        service,
        calendar_id,
        datetime(now.year, now.month, now.day, 21, 0, 0) - timedelta(days=1),
        datetime(now.year, now.month, now.day, 0, 0, 0),
        summary='Sleep',
        color_id=None,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--add',
        action='store_true',
        help='Open a text editor to add text.',
    )
    parser.add_argument(
        '--log',
        type=str,
        help='Path to an Org-mode log file for processing.',
    )
    parser.add_argument(
        '--log-sleep',
        action='store_true',
        help='Add default Sleep events.',
    )
    parser.add_argument(
        'description',
        type=str,
        nargs='?',
        help='Event description.',
    )
    args = parser.parse_args()

    config_path = get_config_path()
    credentials_file = os.path.join(config_path, 'credentials.json')
    token_file = os.path.join(config_path, 'token.json')
    config_file = os.path.join(config_path, 'config.json')

    with open(config_file, 'r') as file:
        config = json.load(file)
    calendar_id = config.get('calendar_id')
    creds = load_credentials(credentials_file, token_file)
    service = build('calendar', 'v3', credentials=creds)

    # Handle '--add' option
    if args.add:
        add_text(service, calendar_id)
        return

    # Handle '--log' option
    if args.log:
        try:
            with open(args.log, 'r') as log_file:
                log_entry = log_file.read()
            create_events_from_log(log_entry, service, calendar_id)
        except Exception as e:
            print(f'Error processing log file: {e}')
        return

    # Handle '--log-sleep' option
    if args.log_sleep:
        create_default_sleep_events(service, calendar_id)
        return

    # Fallback to interactive description-based workflow
    if args.description:
        event_name = args.description
    else:
        event_name = input('Enter the name of the event: ')

    print('Current time:', datetime.now().strftime('%H:%M:%S'))
    print('Press Enter to start working and to pause/resume.')
    print("Type 'exit' and press Enter to quit.")

    total_time = 0.0
    working = False
    start_time = None

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
            print('\nCtrl-D detected, exiting...')
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
            print('Work paused. Press Enter to resume.')
        else:
            start_time = datetime.now()
            working = True
            print('Working... Press Enter to pause.')

    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(
        f'Total work time in this session: '
        f'{int(hours):02}:{int(minutes):02}:{int(seconds):02}'
    )


if __name__ == '__main__':
    main()


def test_parse_org_log():
    log_entry = """
**** Example task
:LOGBOOK:
CLOCK: [2024-11-20 Wed 12:48]--[2024-11-20 Wed 12:49] =>  0:01
CLOCK: [2024-11-20 Wed 12:47]--[2024-11-20 Wed 12:48] =>  0:01
:END:
"""

    result = parse_org_log(log_entry)
    print(result)
