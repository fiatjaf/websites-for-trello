import os
import redis
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

pool = redis.BlockingConnectionPool(
    max_connections=6,
    timeout=20,
    host=os.environ['REDIS_HOST'],
    port=os.environ['REDIS_PORT'],
    password=os.environ['REDIS_PASSWORD'],
)
redis = redis.StrictRedis(connection_pool=pool)

db = SQLAlchemy()

if os.environ.get('DEBUG'):
    os.environ['SITE_URL'] = 'http://' + os.environ['DOMAIN']
    os.environ['API_URL'] = 'http://' + os.environ['DOMAIN'].replace('000', '001')
    os.environ['WEBHOOK_URL'] = 'http://' + os.environ['DOMAIN'].replace('000', '002')
else:
    os.environ['SITE_URL'] = 'http://' + os.environ['DOMAIN']
    os.environ['API_URL'] = 'http://api.' + os.environ['DOMAIN']
    os.environ['WEBHOOK_URL'] = 'http://webhooks.' + os.environ['DOMAIN']

app = Flask(__name__)
app.config.update(os.environ)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
# app.config['SQLALCHEMY_ECHO'] = os.environ.get('DEBUG')

db.init_app(app)
