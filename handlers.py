from app import db
from models import User, Board, List, Card, Label, Comment
from trello import TrelloApi
from helpers import extract_card_cover
from initial_fetch import initial_fetch
from webmention_handling import publish_to_bridgy
import requests
import os

trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])

def createCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    if not card:
        card = Card(
            id=data['card']['id'],
            shortLink=data['card']['shortLink'],
            name=data['card']['name'],
            list_id=data['list']['id']
        )
    card.pos = trello.cards.get_field('pos', card.id)['_value']
    card.desc = trello.cards.get_field('desc', card.id)['_value']

    db.session.add(card)
    db.session.commit()

emailCard = createCard

def copyCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    if not card:
        card = Card(
            id=data['card']['id'],
            shortLink=data['card']['shortLink'],
            name=data['card']['name'],
            list_id=data['list']['id']
        )
    # this card may be already full of attachments or checklists, we must fetch them all
    c = trello.cards.get(card.id,
                         attachments='true',
                         attachment_fields='name,url,edgeColor,id',
                         checklists='all', checklist_fields='name,pos',
                         fields='pos,desc,due,closed,idLabels,idAttachmentCover')
    card.pos = c['pos']
    card.due = c['due']
    card.desc = c['desc']
    card.closed = c['closed']
    card.labels = c.pop('idLabels')
    card.attachments = {'attachments': c['attachments']}
    card.checklists = {'checklists': c['checklists']}
    if 'idAttachmentCover' in c:
        cover_id = c.pop('idAttachmentCover')
        card.cover = extract_card_cover(cover_id, card.attachments['attachments'])

    db.session.add(card)
    db.session.commit()

def updateCard(data, **kw):
    card = Card.query.get(data['card']['id'])

    for attr in ('pos', 'name', 'desc', 'due'):
        if attr in data['card']:
            setattr(card, attr, data['card'][attr])

    if 'idAttachmentCover' in data['card']:
        cover_id = data['card'].pop('idAttachmentCover')
        card.cover = extract_card_cover(cover_id, card.attachments['attachments'])

    if 'idList' in data['card']:
        card.list_id = data['card']['idList']

    db.session.add(card)
    db.session.commit()

def deleteCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    if card:
        db.session.delete(card)
        db.session.commit()

def moveCardFromBoard(data, **kw):
    if not Board.query.get(data['boardTarget']['id']):
        card = Card.query.get(data['card']['id'])
        db.session.delete(card)
        db.session.commit()

def moveCardToBoard(data, **kw):
    card = Card.query.get(data['card']['id'])
    if not card:
        card = Card(
            id=data['card']['id'],
            name=data['card']['name'],
            shortLink=data['card']['shortLink'],
            list_id=data['list']['id']
        )
        card.pos = trello.cards.get_field('pos', card.id)['_value']
        card.desc = trello.cards.get_field('desc', card.id)['_value']
    else:
        card.board_id = data['board']['id']

    db.session.add(card)
    db.session.commit()

def convertToCardFromCheckItem(data, **kw):
    card = Card.query.get(data['card']['id'])
    if not card:
        card = Card(
            id=data['card']['id'],
            name=data['card']['name'],
            list_id=data['list']['id']
        )
        card.pos = trello.cards.get_field('pos', card.id)['_value']
        card.shortLink = trello.cards.get_field('shortLink', card.id)['_value']
        card.desc = trello.cards.get_field('desc', card.id)['_value']

    cardsource = Card.query.get(data['cardSource']['id'])
    if cardsource:
        for checklist in cardsource.checklists['checklists']:
            for idx, checkItem in enumerate(checklist['checkItems']):
                if checkItem['name'] == data['card']['name']:
                    checklist['checkItems'].pop(idx)
                    break
            else:
                continue
            break

    cardsource.checklists.changed()
    db.session.add(card)
    db.session.add(cardsource)
    db.session.commit()

def addMemberToCard(data, **kw):
    user = User.query.filter_by(_id=data['idMember']).first()
    if not user:
        # create user
        user = User(
            _id=kw['payload']['member']['id'],
            id=kw['payload']['member']['username'],
            email=None,
            premium=False,
        )
        db.session.add(user)

    # add user to card
    card = Card.query.get(data['card']['id'])
    users = set(card.users or [])
    users.add(user._id)
    card.users = list(users)
    card.users.changed()

    db.session.add(card)
    db.session.commit()

def removeMemberFromCard(data, **kw):
    user = User.query.filter_by(_id=data['idMember']).first()
    if not user:
        # create user
        user = User(
            _id=kw['payload']['member']['id'],
            id=kw['payload']['member']['username'],
            email=None,
            premium=False,
        )
        db.session.add(user)

    # remove label from card
    card = Card.query.get(data['card']['id'])
    users = set(card.users or [])
    try:
        users.remove(user._id)
    except KeyError:
        print 'user wasn\'t present, so our job is done.'

    card.users = list(users)
    card.users.changed()

    db.session.add(card)
    db.session.commit()

def addAttachmentToCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    if data['attachment']['id'] not in [a['id'] for a in card.attachments['attachments']]:
        card.attachments['attachments'].append(data['attachment'])
        card.attachments.changed()
        cover_id = trello.cards.get_field('idAttachmentCover', data['card']['id'])['_value']
        card.cover = extract_card_cover(cover_id, card.attachments['attachments'])
        db.session.add(card)
        db.session.commit()

def deleteAttachmentFromCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    card.attachments['attachments'] = [att for att in card.attachments['attachments'] if att['id'] != data['attachment']['id']]
    db.session.add(card)
    db.session.commit()

def addChecklistToCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    if data['checklist']['id'] not in [c['id'] for c in card.checklists['checklists']]:
        checklist = {
            'id': data['checklist']['id'],
            'name': data['checklist']['name'],
            'checkItems': trello.checklists.get_checkItem(data['checklist']['id'], fields='name,pos,state'),
            'pos': trello.checklists.get_field('pos', data['checklist']['id'])['_value']
        }
        card.checklists['checklists'].append(checklist)
        card.checklists.changed()
        db.session.add(card)
        db.session.commit()

def removeChecklistFromCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    card.checklists['checklists'] = [chk for chk in card.checklists['checklists'] if chk['id'] != data['checklist']['id']]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def updateChecklist(data, **kw):
    card_id = trello.checklists.get(data['checklist']['id'], cards='all', card_fields=['id'], checkItems='none', fields='id')['cards']['id']

    card = Card.query.get(card_id)
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    for attr in ('pos', 'name'):
        if attr in data['checklist']:
            checklist[attr] = data['checklist'][attr]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def createCheckItem(data, **kw):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]

    for checkItem in checklist['checkItems']:
        if checkItem['id'] == data['checkItem']['id']:
            break
    else:
        data['checkItem']['pos'] = max([chl.get('pos') for chl in checklist['checkItems']] or [0]) + 1
        checklist['checkItems'].append(data['checkItem'])

        card.checklists.changed()
        db.session.add(card)
        db.session.commit()

def updateCheckItemStateOnCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    checkItem = filter(lambda chi: chi['id'] == data['checkItem']['id'], checklist['checkItems'])[0]
    checkItem['state'] = data['checkItem']['state']

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def deleteCheckItem(data, **kw):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    checklist['checkItems'] = [chi for chi in checklist['checkItems'] if chi['id'] != data['checkItem']['id']]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def updateCheckItem(data, **kw):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    checkItem = filter(lambda chi: chi['id'] == data['checkItem']['id'], checklist['checkItems'])[0]
    for attr in ('name', 'pos'):
        if attr in data['checkItem']:
            checkItem[attr] = data['checkItem'][attr]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def createLabel(data, **kw):
    label = Label.query.get(data['label']['id'])
    if not label:
        label = Label(
            id=data['label']['id'],
            name=data['label']['name'],
            color=requests.get('https://api.trello.com/1/labels/'+data['label']['id'], params={'token': trello._token, 'key': trello._apikey, 'fields': 'color'}).json()['color'],
            board_id=data['board']['id']
        )
    db.session.add(label)
    db.session.commit()

def addLabelToCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    label = Label.query.get(data['label']['id'])
    label.color = data['label'].get('color')

    labels = set(card.labels or [])
    labels.add(label.id)
    card.labels = list(labels)
    card.labels.changed()

    db.session.add(label)
    db.session.add(card)
    db.session.commit()

def updateLabel(data, **kw):
    label = Label.query.get(data['label']['id'])
    for attr in ('color', 'name'):
        if attr in data['label']:
            setattr(label, attr, data['label'][attr])

    db.session.add(label)
    db.session.commit()

def deleteLabel(data, **kw):
    label = Label.query.get(data['label']['id'])
    if label:
        db.session.delete(label)
        db.session.commit()

def removeLabelFromCard(data, **kw):
    card = Card.query.get(data['card']['id'])
    label = Label.query.get(data['label']['id'])

    labels = set(card.labels or [])
    try:
        labels.remove(label.id)
    except KeyError:
        print 'label wasn\'t present, so our job is done.'

    card.labels = list(labels)
    card.labels.changed()

    db.session.add(card)
    db.session.commit()

def createList(data, **kw):
    list = List.query.get(data['list']['id'])
    if not list:
        list = List(
            id=data['list']['id'],
            name=data['list']['name'],
            board_id=data['board']['id'],
            closed=False
        )
    list.pos = trello.lists.get_field('pos', list.id)['_value']

    db.session.add(list)
    db.session.commit()

def updateList(data, **kw):
    list = List.query.get(data['list']['id'])
    keychanged = data['old'].keys()[0]
    setattr(list, keychanged, data['list'][keychanged])

    db.session.add(list)
    db.session.commit()

def moveListFromBoard(data, **kw):
    if not data['boardTarget']['id']:
        list = List.query.get(data['list']['id'])
        db.session.delete(list)
        db.session.commit()

def moveListToBoard(data, **kw):
    list = List.query.get(data['list']['id'])
    if not list:
        list = List(
            id=data['list']['id'],
            name=data['list']['name'],
            board_id=data['board']['id'],
            closed=False
        )
        list.pos = trello.lists.get_field('pos', list.id)['_value']
    else:
        list.board_id = data['board']['id']

    db.session.add(list)
    db.session.commit()

def updateBoard(data, **kw):
    board = Board.query.get(data['board']['id'])

    if 'closed' in data['old']:
        if data['old']['closed'] == False and data['board']['closed'] == True:
            # board closed, remove it from the database
            db.session.delete(board)
        elif data['old']['closed'] == True and data['board']['closed'] == False:
            # board reopened, add it again to the database
            initial_fetch(data['board']['id'], username=kw['payload']['memberCreator']['username'])
    else:
        keychanged = data['old'].keys()[0]
        setattr(board, keychanged, data['board'][keychanged])
        db.session.add(board)
    db.session.commit()

def commentCard(data, **kw):
    id = kw['payload']['id']
    comment = Comment.query.get(id)
    if not comment:
        command = data['text'].strip(' .,/.;]=-1234567890<>:?}+_)(*&$#@!"^~\'\n\t\r')
        if command in ['facebook', 'twitter']:
            # comment has the special meaning of saying "publish this for me!"
            silo = command
            publish_to_bridgy(silo, board_id=data['board']['id'], card_id=data['card']['id'])
        else:
            # add comment to database
            comment = Comment(
                id=id,
                card_id=data['card']['id'],
                creator_id=kw['payload']['memberCreator']['id']
            )
            comment.raw = data['text']
            db.session.add(comment)
            db.session.commit()

def updateComment(data, **kw):
    comment = Comment.query.get(data['action']['id'])
    comment.raw = data['action']['text']
    db.session.add(comment)
    db.session.commit()

def deleteComment(data, **kw):
    comment = Comment.query.get(data['action']['id'])
    db.session.delete(comment)
    db.session.commit()

def removeMemberFromBoard(data, **kw):
    payload = kw['payload']
    if os.environ['TRELLO_BOT_ID'] == payload['member']['id']:
        board = Board.query.get(data['board']['id'])
        if board:
            db.session.delete(board)
            db.session.commit()
