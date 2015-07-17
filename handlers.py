from app import db
from models import User, Board, List, Card, Label
from trello import TrelloApi
import os

trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])

def createCard(data):
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

def updateCard(data):
    q = Card.query.filter_by(id=data['card']['id'])

    update = {}
    for attr in ('pos', 'name', 'desc', 'due'):
        if attr in data['card']:
            update[attr] = data['card'][attr]

    if 'idAttachmentCover' in data['card']:
        update['cover'] = data['card']['idAttachmentCover']
    if 'idList' in data['card']:
        update['list_id'] = data['card']['idList']

    q.update(update)
    db.session.commit()

def deleteCard(data):
    card = Card.query.get(data['card']['id'])
    db.session.delete(card)
    db.session.commit()

def moveCardFromBoard(data):
    if not Board.query.get(data['boardTarget']['id']):
        card = Card.query.get(data['card']['id'])
        db.session.delete(card)
        db.session.commit()

def moveCardToBoard(data):
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

def convertToCardFromCheckItem(data):
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

def addAttachmentToCard(data):
    card = Card.query.get(data['card']['id'])
    card.attachments['attachments'] = card.attachments['attachments'] + [data['attachment']]
    db.session.add(card)
    db.session.commit()

def deleteAttachmentFromCard(data):
    card = Card.query.get(data['card']['id'])
    card.attachments['attachments'] = [att for att in card.attachments['attachments'] if att['id'] != data['attachment']['id']]
    db.session.add(card)
    db.session.commit()

def addChecklistToCard(data):
    card = Card.query.get(data['card']['id'])
    checklist = {
        'id': data['checklist']['id'],
        'name': data['checklist']['name'],
        'checkItems': trello.checklists.get_checkItem(data['checklist']['id'], fields='name,pos,state'),
        'pos': trello.checklists.get_field('pos', data['checklist']['id'])
    }
    card.checklists['checklists'].append(checklist)

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def removeChecklistFromCard(data):
    card = Card.query.get(data['card']['id'])
    card.checklists['checklists'] = [chk for chk in card.checklists['checklists'] if chk['id'] != data['checklist']['id']]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def updateChecklist(data):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    for attr in ('pos', 'name'):
        if attr in data['checklist']:
            checklist[attr] = data['checklist'][attr]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def createCheckItem(data):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]

    for checkItem in checklist['checkItems']:
        if checkItem['id'] == data['checkItem']['id']:
            break
    else:
        data['checkItem']['pos'] = max(chl.get('pos') for chl in checklist['checkItems']) + 1
        checklist['checkItems'].append(data['checkItem'])

        card.checklists.changed()
        db.session.add(card)
        db.session.commit()

def updateCheckItemStateOnCard(data):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    checkItem = filter(lambda chi: chi['id'] == data['checkItem']['id'], checklist['checkItems'])[0]
    checkItem['state'] = data['checkItem']['state']

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def deleteCheckItem(data):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    checklist['checkItems'] = [chi for chi in checklist['checkItems'] if chi['id'] == data['checkItem']['id']]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def updateCheckItem(data):
    card = Card.query.get(data['card']['id'])
    checklist = filter(lambda chk: chk['id'] == data['checklist']['id'], card.checklists['checklists'])[0]
    checkItem = filter(lambda chi: chi['id'] == data['checkItem']['id'], checklist['checkItems'])[0]
    for attr in ('name', 'pos'):
        if attr in data['checkItem']:
            checkItem[attr] = data['checkItem'][attr]

    card.checklists.changed()
    db.session.add(card)
    db.session.commit()

def createLabel(data):
    label = Label.query.get(data['label']['id'])
    if not label:
        label = Label(
            id=data['label']['id'],
            name=data['label']['name'],
            board_id=data['board']['id']
        )
    db.session.add(label)
    db.session.commit()

def addLabelToCard(data):
    card = Card.query.get(data['card']['id'])
    label = Label.query.get(data['label']['id'])
    label.color = data['label'].get('color')

    labels = set(card.labels or [])
    labels.add(label.id)
    cards.labels = list(labels)

    db.session.add(label)
    db.session.add(card)
    db.session.commit()

def updateLabel(data):
    label = Label.query.get(data['label']['id'])
    for attr in ('color', 'name'):
        if attr in data['label']:
            setattr(label, attr, data['label'][attr])
    db.session.add(label)
    db.session.commit()

def deleteLabel(data):
    label = Label.query.get(data['label']['id'])
    db.session.delete(label)
    db.session.commit()

def removeLabelFromCard(data):
    card = Card.query.get(data['card']['id'])
    label = Label.query.get(data['label']['id'])

    labels = set(card.labels or [])
    labels.remove(label.id)
    card.labels = labels

    db.session.add(label)
    db.session.add(card)
    db.session.commit()

def createList(data):
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

def updateList(data):
    q = List.query.filter_by(id=data['list']['id'])
    keychanged = data['old'].keys()[0]
    q.update({keychanged: data['list'][keychanged]})
    db.session.commit()

def moveListFromBoard(data):
    if not data['boardTarget']['id']:
        list = List.query.get(data['list']['id'])
        db.session.delete(list)
        db.session.commit()

def moveListToBoard(data):
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

def updateBoard(data):
    board = Board.query.get(data['board']['id'])
    keychanged = data['old'].keys()[0]
    setattr(board, keychanged, data['board'][keychanged])
    db.session.add(board)
    db.session.commit()
