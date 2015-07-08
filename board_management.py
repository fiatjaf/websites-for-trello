from app import db
from models import Board, List, Card, Label
from trello import TrelloApi

def board_create(user_token, name):
    trello = TrelloApi(TRELLO_API_KEY, user_token)
    pass

def board_setup(user_token, id):
    trello = TrelloApi(TRELLO_API_KEY, user_token)
    pass

def initial_fetch(id):
    trello = TrelloApi(TRELLO_BOT_API_KEY, TRELLO_BOT_TOKEN)
    pass
