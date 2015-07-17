import os

if 'localhost' in os.environ.get('DATABASE_URL'):
    from app import db, app
    import models

    with app.app_context():
        db.drop_all()
else:
    print 'not using the development db, will not do anything.'

