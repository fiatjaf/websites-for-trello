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
    Promise.all [
      r.session.user
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((user, db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      user
      trello.getAsync "/1/members/#{user}/boards", {filter: 'open'}
      conn.queryAsync('''
SELECT boards.id, boards.name, subdomain, "shortLink", users.plan AS plan
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE users.id = $1
ORDER BY boards.name
      ''', [user])
      conn.queryAsync('SELECT plan FROM users WHERE id = $1', [user])
    ]
  ).spread((username, boards, bqresult, pqresult) ->
    w.send
      user: username
      premium: pqresult[0].plan == 'premium'
      boards: boards
      activeboards: bqresult.rows
  ).finally(-> release())

module.exports = app
