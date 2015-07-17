import sys
from app import app, db
from models import User, Board, List, Card, Label
from trello import TrelloApi
import requests
import os

def initial_fetch(id, username=None, user_token=None):
    print ':: MODEL-UPDATES :: initial_fetch for', id

    # user (only if user_token is present -- i.e., the first fetch)
    if username and user_token:
        trello = TrelloApi(os.environ['TRELLO_API_KEY'], user_token)
        u = trello.members.get(username, fields=['username', 'email', 'fullName',
                                                 'bio', 'gravatarHash', 'avatarHash'])
        u['_id'] = u['id']
        u['id'] = u.pop('username')

        q = User.query.filter_by(id=username)
        if q.count():
            print ':: MODEL-UPDATES :: found, updating, user', u['id']
            q.update(u)
        else:
            print ':: MODEL-UPDATES :: not found, creating, user', u['id']
            user = User(**u)
            db.session.add(user)

    trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])

    # board
    b = trello.boards.get(id, fields=['name', 'desc', 'shortLink'])

    q = Board.query.filter_by(id=id)
    if q.count():
        print ':: MODEL-UPDATES :: found, updating, board', b['id']
        q.update(b)
    else:
        print ':: MODEL-UPDATES :: not found, creating, board', b['id']
        board = Board(**b)
        if username:
            board.user_id = username
        board.subdomain = b['shortLink']
        db.session.add(board)

    # lists
    for l in trello.boards.get_list(id, fields=['name', 'closed', 'pos', 'idBoard']):
        l['board_id'] = l.pop('idBoard')

        q = List.query.filter_by(id=l['id'])
        if q.count():
            print ':: MODEL-UPDATES :: found, updating, list', l['id']
            q.update(l)
        else:
            print ':: MODEL-UPDATES :: not found, creating, list', l['id']
            list = List(**l)
            db.session.add(list)

        # cards
        for c in trello.lists.get_card(l['id']):
            c = trello.cards.get(c['id'],
                                 attachments='true',
                                 attachment_fields=['name', 'url', 'edgeColor', 'id'],
                                 checklists='all', checklist_fields=['name', 'pos'],
                                 fields=['name', 'pos', 'desc', 'due',
                                         'idAttachmentCover', 'shortLink', 'idList'])
            c['list_id'] = c.pop('idList')

            # transform attachments and checklists in json objects
            c['attachments'] = {'attachments': c['attachments']}
            c['checklists'] = {'checklists': c['checklists']}

            # extract the card cover
            cover = None
            if 'idAttachmentCover' in c:
                cover_id = c.pop('idAttachmentCover')
                covers = filter(lambda a: a['id'] == cover_id, c['attachments']['attachments'])
                if covers:
                    cover = covers[0]['url']
            c['cover'] = cover

            q = Card.query.filter_by(id=c['id'])
            if q.count():
                print ':: MODEL-UPDATES :: found, updating, card', c['id']
                q.update(c)
            else:
                print ':: MODEL-UPDATES :: not found, creating, card', c['id']
                card = Card(**c)
                db.session.add(card)

    # final commit
    print ':: MODEL-UPDATES :: COMMITING INITIAL FETCH FOR', id
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        initial_fetch(sys.argv[1])
