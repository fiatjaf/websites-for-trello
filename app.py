import os
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy()

app = Flask(__name__)
app.config.update(os.environ)

db.init_app(app)
