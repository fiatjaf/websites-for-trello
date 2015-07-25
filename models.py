import datetime
from mistune import BlockLexer
from slugify import slugify
from unidecode import unidecode

from app import db
from sqlalchemy import event
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.mutable import MutableDict
from mutablelist import MutableList

class User(db.Model):
    __tablename__ = 'users'

    # meta
    _id = db.Column(db.String(50))
    id = db.Column(db.String(50), primary_key=True)
    token = db.Column(db.String(100))
    custom_domain_enabled = db.Column(db.Boolean)
    custom_domain_paypal_agreement_id = db.Column(db.String(50))
    boards = db.relationship('Board', backref='user', lazy='dynamic')
    # ~

    email = db.Column(db.Text)
    fullName = db.Column(db.Text)
    bio = db.Column(db.Text)
    gravatarHash = db.Column(db.String(32))
    avatarHash = db.Column(db.String(32))
    registered_on = db.Column(db.DateTime, default=db.func.now())

class Board(db.Model):
    __tablename__ = 'boards'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    shortLink = db.Column(db.String(35), unique=True)
    webhook = db.Column(db.String(50))
    user_id = db.Column(db.String(50), db.ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    subdomain = db.Column(db.Text, index=True, unique=True, nullable=False)
    lists = db.relationship('List', backref='board', lazy='dynamic')
    labels = db.relationship('Label', backref='board', lazy='dynamic')
    # ~

    name = db.Column(db.Text)
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
    cards = db.relationship('Card', backref='list', lazy='dynamic')
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
    comments = db.relationship('Comment', backref='card', lazy='dynamic')
    # ~

    name = db.Column(db.Text, index=True, nullable=False) # indexed because is used to filter standalone pages
    pageTitle = db.Column(db.Text)
    desc = db.Column(db.Text)
    pos = db.Column(db.BigInteger)
    due = db.Column(db.DateTime)
    checklists = db.Column(MutableDict.as_mutable(JSONB), default={'checklists': []})
    attachments = db.Column(MutableDict.as_mutable(JSONB), default={'attachments': []})
    labels = db.Column(MutableList.as_mutable(ARRAY(db.Text, dimensions=1)), default=[]) # bizarre card x label relationship with arrays
    cover = db.Column(db.Text)
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

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

class Comment(db.Model):
    __tablename__ = 'comments'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    card_id = db.Column(db.String(50), db.ForeignKey('cards.id', ondelete="CASCADE"))
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

def update_is_pages(target, value, oldvalue, initiator):
    target.pagesList = value.startswith('#')

event.listen(List.name, 'set', update_is_pages)
