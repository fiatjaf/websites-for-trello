import datetime

from flask.ext.script import Manager

from app import app, db, redis
from models import *

manager = Manager(app)


@manager.command
def stats(year=datetime.date.today().year, month=datetime.date.today().month):
    pvkeys = redis.keys('pageviews:%s:%s:*' % (year, month))
    pvvalues = redis.mget(pvkeys)
    whkeys = redis.keys('webhooks:%s:%s:*' % (year, month))
    whvalues = redis.mget(whkeys)

    _, year, month, _ = pvkeys[0].split(':')
    pvids = [k.split(':')[-1] for k in pvkeys]
    whids = [k.split(':')[-1] for k in whkeys]
    ids = set(pvids + whids)
    pv = dict(zip(pvids, map(int, pvvalues)))
    wh = dict(zip(whids, map(int, whvalues)))
    boards = []
    for id in ids:
        boards.append((pv.get(id, 0), wh.get(id, 0), id))

    print '%7s %26s %27s %5s %5s' % ('month', 'subdomain', 'user', 'PV', 'WH')
    for pvv, whv, id in sorted(boards):
        board = Board.query.get(id)
        if board:
            print '%2s/%s %26s %27s %5d %5d' % (month, year, board.subdomain, board.user_id, pvv, whv)
        else:
            print '%2s/%s %54s %5d %5d' % (month, year, id, pvv, whv)

if __name__ == "__main__":
    manager.run()
