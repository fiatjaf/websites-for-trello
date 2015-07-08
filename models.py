import datetime
from mistune import BlockLexer
from slugify import slugify
from unidecode import unidecode

import settings
from app import db
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.mutable import MutableDict

def calc_visibility(context):
    name = context.current_parameters.get('name', '')
    dashed = name.startswith('_') or name.startswith('#')
    return not dashed

def calc_is_pages(context):
    name = context.current_parameters.get('name', '')
    jogodavelha = name.startswith('#')
    return jogodavelha

def calc_page_title(context):
    desc = context.current_parameters.get('desc', '')
    b = BlockLexer()
    elements = b.parse(desc)
    if elements:
        for elem in elements:
            if elem['type'] == 'newline':
                continue
            elif elem['type'] == 'heading':
                return elem['text']
            else:
                return None

def calc_slug(context):
    ascii_name = context.current_parameters.get('name')
    return slugify(ascii_name, to_lower=True) if ascii_name else None

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
    user_id = db.Column(db.String(50), db.ForeignKey('users.id', ondelete="CASCADE"))
    subdomain = db.Column(db.Text, index=True, unique=True)
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
    slug = db.Column(db.Text, index=True, default=calc_slug, onupdate=calc_slug)
    board_id = db.Column(db.String(50), db.ForeignKey('boards.id', ondelete="CASCADE"))
    cards = db.relationship('Card', backref='list', lazy='dynamic')
    # ~

    name = db.Column(db.Text)
    pos = db.Column(db.Integer)
    closed = db.Column(db.Boolean)
    visible = db.Column(db.Boolean, index=True, default=calc_visibility, onupdate=calc_visibility)
    pagesList = db.Column(db.Boolean, index=True, default=calc_is_pages, onupdate=calc_is_pages)
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    @property
    def created_on(self):
        return datetime.datetime.fromtimestamp(int(self.id[0:8], 16))

class Card(db.Model):
    __tablename__ = 'cards'

    # meta
    id = db.Column(db.String(50), primary_key=True)
    shortLink = db.Column(db.String(35), unique=True)
    slug = db.Column(db.Text, index=True, default=calc_slug, onupdate=calc_slug)
    list_id = db.Column(db.String(50), db.ForeignKey('lists.id', ondelete="CASCADE"))
    comments = db.relationship('Comment', backref='card', lazy='dynamic')
    # ~

    name = db.Column(db.Text, index=True) # indexed because is used to filter standalone pages
    pageTitle = db.Column(db.Text, default=calc_page_title, onupdate=calc_page_title)
    desc = db.Column(db.Text)
    pos = db.Column(db.Integer)
    due = db.Column(db.DateTime)
    checklists = db.Column(MutableDict.as_mutable(JSONB), default={'checklists': []})
    attachments = db.Column(MutableDict.as_mutable(JSONB), default={'attachments': []})
    labels = db.Column(ARRAY(db.Integer, dimensions=1), default=[]) # bizarre card x label relationship with arrays
    cover = db.Column(db.Text)
    visible = db.Column(db.Boolean, index=True, default=calc_visibility, onupdate=calc_visibility)
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
    slug = db.Column(db.Text, index=True, default=calc_slug, onupdate=calc_slug)
    board_id = db.Column(db.String(50), db.ForeignKey('boards.id', ondelete="CASCADE"))
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
