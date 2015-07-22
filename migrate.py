import sys
import time
import requests
import os
from app import app, db
from models import Board
from initial_fetch import initial_fetch

def migrate(board_id, user_token):
    bbrd = Board.query.get(board_id)
    deleted = False

    # ADD BOT
    r = requests.put('https://api.trello.com/1/boards/' + board_id + '/members/' + os.environ['TRELLO_BOT_ID'], params={
        'key': os.environ['TRELLO_API_KEY'],
        'token': user_token
    }, data={
        'type': 'normal'
    })
    if not r.ok:
        print r.text.strip()
        if r.text.strip() == 'invalid token':
            print 'user has removed this token. proceed.'
            db.session.delete(bbrd)
            deleted = True
        else:
            raise Exception('could not add bot to board.')
    print 'bot added'


    # DELETE OLD WEBHOOK
    if bbrd.webhook and not deleted:
        r = requests.delete('https://api.trello.com/1/webhooks/' + bbrd.webhook, params={
            'key': os.environ['TRELLO_API_KEY'],
            'token': user_token
        })
        if not r.ok:
            print r.text.strip()
            if r.text.strip() == 'The requested resource was not found.':
                print 'webhook already deleted. proceed.'
            elif r.text.strip() == 'invalid token':
                print 'user has removed this token. proceed.'
                db.session.delete(bbrd)
                deleted = True
            else:
                raise Exception('could not delete webhook')
    print 'old webhook deleted'

    if not deleted:
        # INITIAL FETCH
        initial_fetch(board_id)
        print 'initial fetch completed'

        # CREATE WEBHOOK
        r = requests.put('https://api.trello.com/1/webhooks', params={
            'key': os.environ['TRELLO_BOT_API_KEY'],
            'token': os.environ['TRELLO_BOT_TOKEN']
        }, data={
            'callbackURL': os.environ['WEBHOOK_URL'] + '/board',
            'idModel': board_id
        }) 
        if not r.ok:
            print r.text
            raise Exception('could not create webhook')
        print 'new webhook created'

        bbrd.webhook = None
        db.session.add(bbrd)

    db.session.commit()

def migrate_many(page):
    offset = (page-1) * 20
    for board in Board.query \
                      .filter(Board.webhook != None) \
                      .order_by(Board.id) \
                      .offset(offset) \
                      .limit(offset + 20):
        print
        print board.name, board.user.id
        migrate(board.id, board.user.token)
        time.sleep(3)

def migrate_all():
    for board in Board.query:
        print
        print board.name, board.user.id
        migrate(board.id, board.user.token)
        time.sleep(3)

if __name__ == '__main__':
    with app.app_context():
        if sys.argv[1] == 'multiple':
            migrate_many(int(sys.argv[2]))
        elif sys.argv[1] == 'all':
            migrate_all()
        else:
            id = sys.argv[1]
            token = sys.argv[2]
            migrate(id, token)
