import os
import datetime
import requests
from mistune import BlockLexer
from slugify import slugify
from unidecode import unidecode

from app import db
from sqlalchemy import event
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.mutable import MutableDict
from utils.mutablelist import MutableList

class User(db.Model):
    __tablename__ = 'users'

    # meta
    _id = db.Column(db.String(50))
    id = db.Column(db.String(50), primary_key=True)
    boards = db.relationship('Board', backref='user', lazy='dynamic', passive_deletes='all')
    events = db.relationship('Event', backref='user', lazy='dynamic')
    # ~

    email = db.Column(db.Text)
    registered_on = db.Column(db.DateTime, default=db.func.now())

class Event(db.Model):
    __tablename__ = 'events'

    # meta
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id'), nullable=False)
    # ~

    kind = db.Column(db.Text, index=True) # later convert this to enum: ['payment', 'bill', 'plan', ...]
    date = db.Column(db.DateTime, default=db.func.now(), nullable=False)
    cents = db.Column(db.Integer)
    data = db.Column(MutableDict.as_mutable(JSONB), default={})

class Board(db.Model):
    __tablename__ = 'boards'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    shortLink = db.Column(db.String(35), unique=True)
    user_id = db.Column(db.String(50), db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    subdomain = db.Column(db.Text, index=True, unique=True, nullable=False)
    lists = db.relationship('List', backref='board', lazy='dynamic', passive_deletes='all')
    labels = db.relationship('Label', backref='board', lazy='dynamic', passive_deletes='all')
    # ~

    name = db.Column(db.Text, nullable=False)
    desc = db.Column(db.Text)

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

class List(db.Model):
    __tablename__ = 'lists'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    slug = db.Column(db.Text, index=True, nullable=False)
    board_id = db.Column(db.String(50), db.ForeignKey('boards.id', ondelete="CASCADE"), nullable=False)
    cards = db.relationship('Card', backref='list', lazy='dynamic', passive_deletes='all')
    # ~

    name = db.Column(db.Text, nullable=False)
    pos = db.Column(db.BigInteger)
    closed = db.Column(db.Boolean, default=False)
    visible = db.Column(db.Boolean, index=True)
    pagesList = db.Column(db.Boolean, index=True)
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

class Card(db.Model):
    __tablename__ = 'cards'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    shortLink = db.Column(db.String(35), unique=True, nullable=False)
    slug = db.Column(db.Text, index=True, nullable=False)
    list_id = db.Column(db.String(50), db.ForeignKey('lists.id', ondelete="CASCADE"), nullable=False)
    comments = db.relationship('Comment', backref='card', lazy='dynamic', passive_deletes='all')
    # ~

    name = db.Column(db.Text, index=True, nullable=False) # indexed because is used to filter standalone pages
    pageTitle = db.Column(db.Text)
    desc = db.Column(db.Text, nullable=False)
    pos = db.Column(db.BigInteger)
    due = db.Column(db.DateTime)
    checklists = db.Column(MutableDict.as_mutable(JSONB), default={'checklists': []})
    attachments = db.Column(MutableDict.as_mutable(JSONB), default={'attachments': []})
    labels = db.Column(MutableList.as_mutable(ARRAY(db.Text, dimensions=1)), default=[]) # bizarre card x label relationship with arrays
    users = db.Column(MutableList.as_mutable(ARRAY(db.Text, dimensions=1)), default=[]) # bizarre card x user relationship with arrays
    cover = db.Column(db.Text)
    syndicated = db.Column(MutableList.as_mutable(ARRAY(db.Text, dimensions=1)), default=[]) # an array to store URLs of syndications (posting to Twitter, Facebook etc. with brid.gy)
    closed = db.Column(db.Boolean, default=False)
    visible = db.Column(db.Boolean, index=True)
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

    @staticmethod
    def with_date(cards):
        cards = [cards] if not hasattr(cards, '__iter__') else cards
        for card in cards:
            card.date = card.due or card.created_on
            yield card

class Label(db.Model):
    __tablename__ = 'labels'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    slug = db.Column(db.Text, index=True)
    board_id = db.Column(db.String(50), db.ForeignKey('boards.id', ondelete="CASCADE"), nullable=False)
    # ~

    name = db.Column(db.Text)
    color = db.Column(db.Text)
    visible = db.Column(db.Boolean, index=True)

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

class Comment(db.Model):
    __tablename__ = 'comments'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    card_id = db.Column(db.String(50), db.ForeignKey('cards.id', ondelete="CASCADE"), nullable=False)
    creator_id = db.Column(db.String(50), nullable=False)
    # ~

    raw = db.Column(db.Text)

    # automatically filled
    body = db.Column(db.Text)
    source_url = db.Column(db.Text)
    source_display = db.Column(db.Text)
    author_name = db.Column(db.Text)
    author_url = db.Column(db.Text)
    # ~

    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

# event listeners
def update_slug(target, value, oldvalue, initiator):
    if oldvalue != value or target.slug == None:
        target.slug = slugify(value, to_lower=True) if value else None

event.listen(Card.name, 'set', update_slug)
event.listen(List.name, 'set', update_slug)
event.listen(Label.name, 'set', update_slug)

def update_page_title(target, value, oldvalue, initiator):
    b = BlockLexer()
    elements = b.parse(value)
    if elements:
        for elem in elements:
            if elem['type'] == 'newline':
                continue
            elif elem['type'] == 'heading':
                target.pageTitle = elem['text']
                break
            else:
                target.pageTitle = None
                break

event.listen(Card.desc, 'set', update_page_title)

def update_visibility(target, value, oldvalue, initiator):
    target.visible = not (value.startswith('_') or value.startswith('#'))

event.listen(Card.name, 'set', update_visibility)
event.listen(List.name, 'set', update_visibility)
event.listen(Label.name, 'set', update_visibility)

def update_is_pages(target, value, oldvalue, initiator):
    target.pagesList = value.startswith('#')

event.listen(List.name, 'set', update_is_pages)

def update_comment(target, value, oldvalue, initiator):
    raw = value
    if target.creator_id == os.environ['TRELLO_BOT_ID']:
        # comment from wftbot
        try:
            # parse comment from webmention
            rawlines = raw.splitlines()
            target.body = '\n'.join(map(lambda l: l[2:], rawlines[2:-2])) + " "
            target.author_name = rawlines[0].split('**[')[1].split('](')[0]
            target.author_url = rawlines[0].split('](')[1].split(')')[0]
            target.source_display = rawlines[-1].split('via _[')[1].split('](')[0]
            target.source_url = rawlines[-1].split('](')[1].split(')')[0]
        except IndexError:
            # other special comments made by the bot, just leave it there, with a NULL body.
            print 'comment made by wft that is not a webmention. ignore.'
    else:
        # normal comment, use full text as body.
        target.body = raw
        target.author_name = requests.get('https://api.trello.com/1/members/'+target.creator_id+'/username').json()['_value']
        target.author_url = 'https://trello.com/' + target.creator_id
        target.source_display = 'trello.com'
        target.source_url = 'https://trello.com/c/' + target.card_id

event.listen(Comment.raw, 'set', update_comment)
