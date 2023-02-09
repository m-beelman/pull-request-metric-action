import os
from datetime import datetime
import json
import sys

def convert_to_datetime(date_string: str):
    if (date_string == None):
        return None
    return datetime.fromisoformat(date_string.replace('Z', '+00:00'))

def get_detailed_pull_request_event_history(pr_id: int):
    return os.popen(f'gh pr view {pr_id} --json commits,reviews,state,comments,closedAt,createdAt,mergedAt,changedFiles,additions,deletions').read()

def categorize_event_result(result):
    categorized_result = {}
    categorized_result['commits'] = result['commits']
    categorized_result['reviews'] = result['reviews']
    categorized_result['state'] = result['state'] 
    categorized_result['comments'] = result['comments']
    categorized_result['closedAt'] = result['closedAt']
    categorized_result['createdAt'] = result['createdAt']
    categorized_result['mergedAt'] = result['mergedAt']
    categorized_result['changedFiles'] = result['changedFiles']
    categorized_result['additions'] = result['additions']
    categorized_result['deletions'] = result['deletions']
    return categorized_result

def generate_event_timeline(categories: dict):
    events = []

    # merge all interesting events into a single list
    events.append([{'type': 'createAt', 'date': convert_to_datetime(categories['createdAt']), 'event_instance':categories['createdAt']}])
    events.append([{'type': 'commit', 'date': convert_to_datetime(commit['committedDate']), 'event_instance':commit} for commit in categories['commits']])
    events.append([{'type': 'review', 'date': convert_to_datetime(review['submittedAt']), 'event_instance':review} for review in categories['reviews']])
    events.append([{'type': 'mergedAt', 'date': convert_to_datetime(categories['mergedAt']), 'event_instance':categories['mergedAt']}])
    events.append([{'type': 'closedAt', 'date': convert_to_datetime(categories['closedAt']), 'event_instance':categories['closedAt']}])

    #flatten the list
    events = [item for sublist in events for item in sublist]

    # filter out events that don't have a valid date
    events = [event for event in events if event['date'] != None]

    # sort the events by date
    events.sort(key=lambda x: x['date'])


    # now, create a list of events with the time between events
    events_with_time = []


    # calculate the time between events
    for i in range(len(events)):
        if i == 0:
            events_with_time.append({'type': events[i]['type'], 'date': events[i]['date'], 'time': 0})
        else:
            events_with_time.append({'type': events[i]['type'], 'date': events[i]['date'], 'time': (events[i]['date'] - events[i-1]['date']).total_seconds()})

    return events_with_time

def get_first_event_of_type(events_with_time: list, type: str):
    return next((event for event in events_with_time if event['type'] == type), None)

def get_last_event_of_type(events_with_time: list, type: str):
    return next((event for event in reversed(events_with_time) if event['type'] == type), None)

def get_time_spend_on_branch_before_pr_created_from_timeline(events_with_time: list):
    first_commit = get_first_event_of_type(events_with_time, 'commit')
    first_create = get_first_event_of_type(events_with_time, 'createAt')
    return (first_create['date'] - first_commit['date']).total_seconds()


def calc_time_diff_between_events(event1: dict, event2: dict):
    if event1 == None or event2 == None:
        return 0
    return (event1['date'] - event2['date']).total_seconds()

def get_time_spend_on_pr_after_creation(events_with_time: list):
    first_create = get_first_event_of_type(events_with_time, 'createAt')
    first_merge = get_first_event_of_type(events_with_time, 'mergedAt')
    return calc_time_diff_between_events(first_merge, first_create)

def get_time_to_merge_after_last_review(event_with_time: list):
    last_review = get_last_event_of_type(events_with_time, 'review')
    first_merge = get_first_event_of_type(events_with_time, 'mergedAt')
    return calc_time_diff_between_events(first_merge, last_review)
    
def get_time_spend_on_branch_until_merged(events_with_time: list):
    time_spend_on_branch = 0
    for i in range(len(events_with_time)):
        time_spend_on_branch += events_with_time[i]['time']
        if events_with_time[i]['type'] == 'mergedAt' or events_with_time[i]['type'] == 'closedAt':
            break
    return time_spend_on_branch

def create_pr_markdown_comment(events_with_time: list, categorized_result: dict):
    # calculate the metrics
    time_spend_on_branch_before_pr_created = get_time_spend_on_branch_before_pr_created_from_timeline(events_with_time)
    time_spend_on_branch = get_time_spend_on_branch_until_merged(events_with_time)
    time_to_merge_after_last_review = get_time_to_merge_after_last_review(events_with_time)
    time_spend_on_pr_after_creation = get_time_spend_on_pr_after_creation(events_with_time)
    
    return f'''
    ## Pull Request Metrics
    ### Duration Metrics
    |Metric description|Duration|Duration in seconds|
    |---|---|---|
    |Time that was spend on the branch before the PR was created|{convert_seconds_to_a_readable_string(time_spend_on_branch_before_pr_created)}|{time_spend_on_branch_before_pr_created}|
    |Time that was spend on the branch before the PR was merged| {convert_seconds_to_a_readable_string(time_spend_on_branch)} |{time_spend_on_branch}|
    |Time to merge after the last review| {convert_seconds_to_a_readable_string(time_to_merge_after_last_review)} |{time_to_merge_after_last_review}|
    |Time spend on the PR after creation| {convert_seconds_to_a_readable_string(time_spend_on_pr_after_creation)} |{time_spend_on_pr_after_creation}|

    ### PR Metrics
    |Description|Value|
    |---|---|
    |Changed files count|{categorized_result['changedFiles']}|
    |Commit count|{len(categorized_result['commits'])}|
    |Additions|{categorized_result['additions']}|
    |Deletions|{categorized_result['deletions']}|
    |Comment count|{len(categorized_result['comments'])}|
    |Review count|{len(categorized_result['reviews'])}|
    '''
    

def convert_seconds_to_a_readable_string(time_in_seconds: int):
    time_in_seconds = int(time_in_seconds)
    if time_in_seconds < 60:
        return f'{time_in_seconds} seconds'
    elif time_in_seconds < 3600:
        return f'{time_in_seconds//60} minutes'
    elif time_in_seconds < 86400:
        return f'{time_in_seconds//3600} hours'
    elif time_in_seconds < 604800:
        return f'{time_in_seconds//86400} days'
    elif time_in_seconds < 2629743:
        return f'{time_in_seconds//604800} weeks'
    else:
        return f'{time_in_seconds//2629743} months'

def write_comment_to_file(file_path:str, comment:str):
    with open(file_path, 'w') as file:
        file.write(comment)


pr_id = int(sys.argv[1])
comment_file_path = sys.argv[2]

result = get_detailed_pull_request_event_history(pr_id)
# create object from json string result
result = json.loads(result)

categorize_result = categorize_event_result(result)

events_with_time = generate_event_timeline(categorize_result)

pr_comment_string = create_pr_markdown_comment(events_with_time, categorize_result)

write_comment_to_file(comment_file_path, pr_comment_string)