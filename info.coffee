express       = require 'express'
Promise       = require 'bluebird'

{ trello, pg, } = require './settings'
{ userRequired } = require './lib'

app = express()

app.get '/', (r, w) ->
  if not r.session.token
    return w.sendStatus 204

  trello.token = r.session.token
  release = null

  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      trello.getAsync "/1/members/#{r.session.userid}/boards", {filter: 'open'}
      conn.queryAsync('''
SELECT boards.id, boards.name, subdomain, "shortLink", users.plan AS plan
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE users._id = $1
ORDER BY boards.name
      ''', [r.session.userid])
      conn.queryAsync('SELECT plan FROM users WHERE _id = $1', [r.session.userid])
    ]
  ).spread((boards, bqresult, pqresult) ->
    w.send
      user: r.session.user
      premium: pqresult.rows[0].plan == 'premium'
      boards: boards
      activeboards: bqresult.rows
  ).finally(-> release())

module.exports = app
