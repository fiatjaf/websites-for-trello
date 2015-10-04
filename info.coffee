express       = require 'express'
Promise       = require 'bluebird'

{
  trello,
  pg,
} = require './settings'
{
  userRequired
} = require './lib'

app = express()

app.get '/', (request, response, next) ->
  if not request.session.token
    return response.sendStatus 204

  trello.token = request.session.token
  release = null

  Promise.resolve().then(->
    Promise.all [
      (request.session.user or trello.getAsync "/1/token/#{trello.token}/member/username")
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((user, db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      (user._value or user)
      trello.getAsync "/1/members/#{user._value or user}/boards", {filter: 'open'}
      conn.queryAsync('''
SELECT boards.id, boards.name, subdomain, "shortLink"
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE users.id = $1
ORDER BY boards.name
                      ''', [user._value or user])
      conn.queryAsync('''
SELECT premium
FROM premium_accounts
WHERE user_id = $1
                      ''', [user._value or user])
    ]
  ).spread((username, boards, bqresult, pqresult) ->
    request.session.user = username

    response.send
      user: username
      premium: if pqresult.rows.length then pqresult.rows[0].premium else false
      boards: boards
      activeboards: bqresult.rows
  ).catch(next).finally(-> release())

app.get '/money', userRequired, (request, response, next) ->
  release = null
  Promise.resolve().then(->
    Promise.all [
      (request.session.user or trello.getAsync "/1/token/#{trello.token}/member/username")
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((user, db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      conn.queryAsync '''
SELECT
  to_char(date, 'TMMonth DD, YYYY') AS date,
  kind,
  cents,
  data->>'description' AS description
FROM events
WHERE user_id = $1
ORDER BY events.date DESC
      ''', [user._value or user]
      conn.queryAsync '''
SELECT sum(c) AS owe FROM (
  SELECT CASE WHEN kind = 'payment' THEN -cents ELSE cents END AS c
  FROM events
  WHERE user_id = $1
)a
      ''', [user._value or user]
    ]
  ).spread((hqres, oqres) ->
    response.send
      history: hqres.rows
      owe: oqres.rows[0].owe
  ).catch(next).finally(-> release())

module.exports = app
