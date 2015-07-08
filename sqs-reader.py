import json
import handlers as h
from board_management import board_setup, board_create, initial_fetch
from boto import sqs

conn = sqs.connect_to_region('us-east-1')
q    = conn.get_queue('trellocms-webhooks')

def process_messages():
    messages = q.get_messages(3)
    for message in messages:
        try:
            process_message(message)
        except Exception, e:
            print e

def process_message(message):
    body = message.get_body()
    payload = json.loads(body)

    if payload['type'] == 'boardCreateAndSetup':
        board_id = board_create(payload['user_token'], payload['board_name'])
        board_setup(payload['user_token'], board_id)
        initial_fetch(board_id, payload['username'])

    elif payload['type'] == 'boardSetup':
        board_setup(payload['user_token'], payload['board_id'])
        initial_fetch(payload['board_id'], payload['username'])

    else:
        handler = getattr(h, payload['type'])
        handler(payload['data'])

if __name__ == '__main__':
    process()

# this is meant to be run as a cron job every 3 seconds or so.
