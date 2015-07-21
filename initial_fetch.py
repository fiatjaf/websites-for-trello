import sys
from app import app, db
from models import User, Board, List, Card, Label
from trello import TrelloApi
import requests
import os

def initial_fetch(id, username=None, user_token=None):
    print ':: MODEL-UPDATES :: initial_fetch for', id

    # to clear things that do not exist anymore in the trello board
    to_delete = set()

    # user (only if user_token is present -- i.e., the first fetch)
    if username and user_token:
        trello = TrelloApi(os.environ['TRELLO_API_KEY'], user_token)
        u = trello.members.get(username, fields=['username', 'email', 'fullName',
                                                 'bio', 'gravatarHash', 'avatarHash'])
        u['_id'] = u['id']
        u['id'] = u.pop('username')

        user = User.query.get(username)
        if user:
            print ':: MODEL-UPDATES :: found, updating, user', u['id']
            for key, value in u.items(): setattr(user, key, value)
        else:
            print ':: MODEL-UPDATES :: not found, creating, user', u['id']
            user = User(**u)
        db.session.add(user)

    trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])

    # board
    b = trello.boards.get(id, fields=['name', 'desc', 'shortLink'])

    board = Board.query.get(id)
    if board:
        print ':: MODEL-UPDATES :: found, updating, board', b['id']
        for key, value in b.items(): setattr(board, key, value)
    else:
        print ':: MODEL-UPDATES :: not found, creating, board', b['id']
        board = Board(**b)
        if username:
            board.user_id = username
        board.subdomain = b['shortLink'].lower()
    db.session.add(board)

    # labels
    for label in board.labels: to_delete.add((Label, label.id))
    for l in requests.get('https://api.trello.com/1/boards/' + id + '/labels', params={'key': trello._apikey, 'token': trello._token, 'fields': 'color,name'}).json():
        to_delete.discard((Label, l['id']))
        l['board_id'] = id

        label = Label.query.get(l['id'])
        if label:
            print ':: MODEL-UPDATES :: found, updating, label', l['id']
            for key, value in l.items(): setattr(label, key, value)
        else:
            print ':: MODEL-UPDATES :: not found, creating, label', l['id']
            label = Label(**l)
        db.session.add(label)

    # lists
    for list in board.lists: to_delete.add((List, list.id))
    for l in trello.boards.get_list(id, fields=['name', 'closed', 'pos', 'idBoard']):
        to_delete.discard((List, l['id']))
        l['board_id'] = l.pop('idBoard')

        list = List.query.get(l['id'])
        if list:
            print ':: MODEL-UPDATES :: found, updating, list', l['id']
            for key, value in l.items(): setattr(list, key, value)
        else:
            print ':: MODEL-UPDATES :: not found, creating, list', l['id']
            list = List(**l)
        db.session.add(list)

        # cards
        for card in list.cards: to_delete.add((Card, card.id))
        for c in trello.lists.get_card(l['id']):
            to_delete.discard((Card, c['id']))
            c = trello.cards.get(c['id'],
                                 attachments='true',
                                 attachment_fields=['name', 'url', 'edgeColor', 'id'],
                                 checklists='all', checklist_fields=['name', 'pos'],
                                 fields=['name', 'pos', 'desc', 'due',
                                         'idLabels',
                                         'idAttachmentCover', 'shortLink', 'idList'])
            c['list_id'] = c.pop('idList')
            c['labels'] = c.pop('idLabels')

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

            card = Card.query.get(c['id'])
            if card:
                print ':: MODEL-UPDATES :: found, updating, card', c['id']
                for key, value in c.items(): setattr(card, key, value)
            else:
                print ':: MODEL-UPDATES :: not found, creating, card', c['id']
                card = Card(**c)
            db.session.add(card)

    for cls, id in to_delete:
        entity = cls.query.get(id)
        print ':: MODEL-UPDATES :: ', entity, 'is not in the trello board anymore. deleting.'
        db.session.delete(entity)

    # final commit
    print ':: MODEL-UPDATES :: COMMITING INITIAL FETCH FOR', id
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        initial_fetch(sys.argv[1])
