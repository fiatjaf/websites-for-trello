import os
import sys
import math
import time
import json
import shelve
import requests
import traceback
import handlers as h
from board_management import board_setup
from initial_fetch import initial_fetch
from app import app

pwd = os.path.dirname(os.path.realpath(__file__))
counts = shelve.open(os.path.join(pwd, 'counts.store'))

def process_messages(n=10):
    r = requests.get(os.environ['WEBHOOK_URL'] + '/messages', params={'n': n})

    messages = []
    try:
        messages = json.loads(r.text)
    except ValueError:
        print ':: MODEL-UPDATES :: response from the queue server:', r.text
        traceback.print_exc(file=sys.stdout)

    if messages:
        payloads = []
        for message in messages:
            body = message['message']
            payload = json.loads(body)
            payload['message'] = message
            payloads.append(payload)

        s = sorted(payloads, key=lambda m: m.get('date'))

        #print ':: MODEL-UPDATES :: sorted/unsorted/type'
        #for i in range(len(s)):
        #    print '\t{} | {} | {}'.format(payloads[i].get('date'), s[i].get('date'), s[i].get('type'))

        for payload in s:
            with app.app_context():
                try:
                    process_message(payload)
                except Exception:
                    print ':: MODEL-UPDATES :: payload:', payload
                    traceback.print_exc(file=sys.stdout)
            # delete message
            requests.delete(os.environ['WEBHOOK_URL'] + '/messages/%s' % payload['message']['id'])

def process_message(payload):
    print ':: MODEL-UPDATES :: processing message', payload.get('date'), payload.get('type')#, payload.get('data')

    if payload['type'] == 'boardSetup':
        board_id = str(payload['board_id'])
        counts[board_id] = 0

        initial_fetch(payload['board_id'], username=payload['username'], user_token=payload['user_token'])
        board_setup(payload['user_token'], payload['board_id'])

        counts[board_id] = 0

    else:
        board_id = str(payload['data']['board']['id'])

        try:
            handler = getattr(h, payload['type'])
        except AttributeError:
            return

        handler(payload['data'])

        # count up for this board. every x messages we do a initial-fetch
        counts[board_id] = counts.get(board_id, 0) + 1
        if counts[board_id] % 70 == 0:
            board_clear(board_id)
            initial_fetch(board_id)

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'forever':
        while True:
            time.sleep(3)
            process_messages(100)
            time.sleep(3)
    elif len(sys.argv) == 2 and unicode(sys.argv[1]).isnumeric():
        n = int(sys.argv[1])
        process_messages(n)
    else:
        for i in range(9):
            time.sleep(6)
            process_messages(100)

# this is meant to be run as a cron job every 3 seconds or so.
