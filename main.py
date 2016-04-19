import os
import sys
import pika # type: ignore
import math
import time
import json
import signal
import requests
import datetime
import analytics # type: ignore
import traceback
import handlers as h
import redis.exceptions as redis_exceptions # type: ignore
from raygun4py import raygunprovider # type: ignore
from board_management import board_setup, add_bot, remove_bot
from initial_fetch import initial_fetch
from webmention_handling import handle_webmention
from models import Board, User
from app import app, redis

analytics.write_key = os.environ.get('SEGMENT_WRITE_KEY')

class LocalTimeUp(BaseException):
    pass

class MessageCount(BaseException):
    pass

pwd = os.path.dirname(os.path.realpath(__file__))
raygun = raygunprovider.RaygunSender(os.environ['RAYGUN_API_KEY'])
starttime = datetime.datetime.now()

# open connection to cloudamqp
params = pika.URLParameters(os.environ['CLOUDAMQP_URL'])
params.socket_timeout = 5
connection = pika.BlockingConnection(params)
channel = connection.channel()
channel.queue_declare(queue='wft', durable=True)

def main(*args, **kwargs):
    print(':: MODEL-UPDATES :: waiting for messages.')

    # start listening
    listen()

def listen():
    # this is where we actually start listening
    messages = []
    try:
        # local alarm, 20 seconds
        def proceed(signum, frame):
            raise LocalTimeUp('proceed.')
        signal.signal(signal.SIGALRM, proceed)
        signal.alarm(15)

        for method, properties, body in channel.consume(queue='wft'):
            print(':: MODEL-UPDATES :: got a message. now we have %s.') % (len(messages) + 1)
            try:
                messages.append((json.loads(body), method))
            except ValueError:
                print(':: MODEL-UPDATES :: non-json message:'), body
                channel.basic_ack(delivery_tag=method.delivery_tag)

            if len(messages) == 10:
                print(':: MODEL-UPDATES :: got 10, will process.')
                signal.alarm(0)
                raise MessageCount

    except (LocalTimeUp, MessageCount):
        if messages:
            process_message_batch(messages)

        if (datetime.datetime.now() - starttime).seconds > 120:
            # running for more than 120 seconds. stop.
            print(':: MODEL-UPDATES :: end of time.')
            channel.cancel()
            connection.close()
            sys.exit()
        else:
            # not running for enough time yet. restart.
            listen()

def process_message_batch(messages):
    sorted_messages = sorted(messages, key=lambda m: m[0].get('date'))

    #print(':: MODEL-UPDATES :: sorted/unsorted/type')
    #for i in range(len(sorted_messages)):
    #    print '\t{} | {} | {}'.format(payloads[i].get('date'), s[i].get('date'), s[i].get('type'))

    for message, method in sorted_messages:
        payload = message.get('action') or message
        with app.app_context():
            try:
                process_message(payload)
            except Exception:
                print(':: MODEL-UPDATES :: payload (batch level):'), payload
                traceback.print_exc(file=sys.stdout)

        # delete message frm rabbitmq
        channel.basic_ack(delivery_tag=method.delivery_tag)

def process_message(payload):
    print(':: MODEL-UPDATES :: processing {} {}'.format(payload.get('date'), payload.get('type')))

    if payload['type'] == 'boardSetup':
        board_id = str(payload['board_id'])

        try:
            add_bot(payload['user_token'], payload['board_id'])
            board_setup(
                payload['board_id'],
                username=payload['username'],
                is_new=payload.get('is_new')
            )
            user, board = initial_fetch(
                payload['board_id'],
                username=payload['username'],
                user_token=payload['user_token']
            )

            # track user with segment.io
            analytics.identify(user._id, {
                'email': user.email,
                'username': user.id
            })
            analytics.track(user._id, 'boardSetup', {
                'id': board.id,
                'shortLink': board.shortLink,
                'subdomain': board.subdomain,
                'name': board.name
            })
        except:
            raygun.set_user(payload['username'])
            raygun.send_exception(
                exc_info=sys.exc_info(),
                userCustomData={'board_id': payload['board_id']},
                tags=['boardSetup']
            )
            traceback.print_exc(file=sys.stdout)
            print(':: MODEL-UPDATES :: payload:'), payload

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
            print(':: MODEL-UPDATES :: payload:'), payload

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
            print(':: MODEL-UPDATES :: payload:'), payload

    else:
        board = Board.query.get(payload['data']['board']['id'])

        try:
            handler = getattr(h, payload['type'])
            handler(payload['data'], payload=payload)

            # track event with segment.io
            user = User.query.filter_by(id=board.user_id).first()
            analytics.track(user._id, payload['type'], payload['data'])

        except AttributeError as e:
            print(':: MODEL-UPDATES :: AttributeError', e)
            return
        except:
            print('verify if this is a webhook for a board that was deleted: (payload: {})'.format(json.dumps(payload)))
            if not board:
                print(':: MODEL-UPDATES :: webhook for a board not registered anymore.')
                print(':: MODEL-UPDATES :: adding this board to the webhook deletion list.')
                redis.sadd('deleted-board', payload['data']['board']['id'])
            else:
                raygun.set_user(payload['memberCreator']['username'])
                raygun.send_exception(
                    exc_info=sys.exc_info(),
                    userCustomData=payload['data'],
                    tags=['webhook', payload['type']]
                )
                traceback.print_exc(file=sys.stdout)
                print(':: MODEL-UPDATES :: payload:'), payload
                print(':: MODEL-UPDATES :: since this error happened probably due to a mismatch between our database and the live trello board, we will trigger a initial_fetch for %s.' % payload['data']['board']['id'])
                initial_fetch(payload['data']['board']['id'])

        # count webhooks on redis
        today = datetime.date.today()
        try:
            redis.incr('webhooks:%d:%d:%s' % (today.year, today.month, payload['data']['board']['id']))
        except redis_exceptions.ResponseError as e:
            print(':: MODEL-UPDATES ::', e, ') -- couldn\'t INCR webhooks:%d:%d:%s' % (today.year, today.month, payload['data']['board']['id']))

if __name__ == '__main__':
    main()

# this is meant to be run as a cron job every 3 minutes or so.
