import os
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy()

os.environ['SITE_URL'] = 'http://' + os.environ['DOMAIN']
os.environ['API_URL'] = 'http://api.' + os.environ['DOMAIN']
os.environ['WEBHOOK_URL'] = 'http://webhooks.' + os.environ['DOMAIN']
os.environ['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
os.environ['SQLALCHEMY_ECHO'] = os.environ.get('DEBUG')

app = Flask(__name__)
app.config.update(os.environ)

db.init_app(app)
