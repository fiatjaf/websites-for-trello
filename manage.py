from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from app import app, db
import models

manager = Manager(app)

# flask-migrate
Migrate(app, db)
manager.add_command('db', MigrateCommand)

if __name__ == "__main__":
    manager.run()
