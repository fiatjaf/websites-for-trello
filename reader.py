import os
import sys
import math
import time
import json
import shelve
import requests
import datetime
import traceback
import handlers as h
from raygun4py import raygunprovider
from board_management import board_setup, add_bot, remove_bot
from initial_fetch import initial_fetch
from webmention_handling import handle_webmention
from models import Board
from app import app, redis

pwd = os.path.dirname(os.path.realpath(__file__))
raygun = raygunprovider.RaygunSender(os.environ['RAYGUN_API_KEY'])
counts = shelve.open(os.path.join(pwd, 'counts.store'))
starttime = datetime.datetime.now()

def process_messages(n=10):
    r = requests.get(os.environ['WEBHOOK_URL'] + '/messages', params={'n': n})

    messages = []
    try:
        messages = json.loads(r.text)
        if len(messages) > 0:
            print ':: MODEL-UPDATES :: got %s messages.' % len(messages)
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
    print ':: MODEL-UPDATES :: processing', payload.get('date'), payload.get('type')

    if payload['type'] == 'boardSetup':
        board_id = str(payload['board_id'])
        counts[board_id] = 0

        try:
            add_bot(payload['user_token'], payload['board_id'])
            initial_fetch(payload['board_id'], username=payload['username'], user_token=payload['user_token'])
            board_setup(payload['board_id'])
        except:
            raygun.set_user(payload['username'])
            raygun.send_exception(
                exc_info=sys.exc_info(),
                userCustomData={'board_id': payload['board_id']},
                tags=['boardSetup']
            )
            traceback.print_exc(file=sys.stdout)
            print ':: MODEL-UPDATES :: payload:', payload

        counts[board_id] = 0

    elif payload['type'] == 'initialFetch':
        try:
            initial_fetch(payload['board_id'])
        except:
            raygun.send_exception(
                exc_info=sys.exc_info(),
                userCustomData={'board_id': payload['board_id']},
                tags=['initialFetch']
            )
            traceback.print_exc(file=sys.stdout)

    elif payload['type'] == 'boardDeleted':
        board_id = str(payload['board_id'])
        del counts[board_id]

        try:
            remove_bot(payload['board_id'])
        except:
            raygun.set_user(payload['username'])
            raygun.send_exception(
                exc_info=sys.exc_info(),
                userCustomData={'board_id': payload['board_id']},
                tags=['boardDeleted']
            )
            traceback.print_exc(file=sys.stdout)
            print ':: MODEL-UPDATES :: payload:', payload

    elif payload['type'] == 'webmentionReceived':
        try:
            handle_webmention(source=payload['source'], target=payload['target'])
        except:
            raygun.send_exception(
                exc_info=sys.exc_info(),
                userCustomData=payload,
                tags=['webmentionReceived']
            )
            traceback.print_exc(file=sys.stdout)
            print ':: MODEL-UPDATES :: payload:', payload

    else:
        board_id = str(payload['data']['board']['id'])

        try:
            handler = getattr(h, payload['type'])
            handler(payload['data'], payload=payload)
        except AttributeError:
            return
        except:
            if not Board.query.get(payload['data']['board']['id']):
                print ':: MODEL-UPDATES :: webhook for a board not registered anymore.'
            raygun.set_user(payload['memberCreator']['username'])
            raygun.send_exception(
                exc_info=sys.exc_info(),
                userCustomData=payload['data'],
                tags=['webhook', payload['type']]
            )
            traceback.print_exc(file=sys.stdout)
            print ':: MODEL-UPDATES :: payload:', payload

        # count webhooks on redis
        today = datetime.date.today()
        try:
            redis.incr('webhooks:%d:%d:%s' % (today.year, today.month, payload['data']['board']['id']))
        except redis.exceptions.ResponseError:
            print ':: MODEL-UPDATES ::', e, ' -- couldn\'t INCR webhooks:%d:%d:%s' % (today.year, today.month, payload['data']['board']['id'])

        # count up for this board. every x messages we do a initial-fetch
        counts[board_id] = counts.get(board_id, 0) + 1
        if counts[board_id] % 70 == 0:
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
            if (datetime.datetime.now() - starttime).seconds > 59:
                break
            process_messages(100)

# this is meant to be run as a cron job every 3 seconds or so.
