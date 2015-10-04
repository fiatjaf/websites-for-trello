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
FROM users
WHERE users.id = $1
                      ''', [user._value or user])
    ]
  ).spread((username, boards, bqresult, pqresult) ->
    request.session.user = username

    response.send
      user: username
      premium: pqresult.rows[0].premium
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
  left(cents, -2) || '.' || right(cents, -1) AS amount,
  data->>'description' AS description
FROM (
  SELECT date, kind, lpad(cents::text, 3, '0') AS cents, data
  FROM events
  WHERE user_id = $1
  ORDER BY date DESC
)a
      ''', [user._value or user]
      conn.queryAsync '''
SELECT left(cents::text, -2) || '.' || right(cents::text, -1) AS owe
FROM (
  SELECT lpad(sum(c)::text, 3, '0') AS cents FROM (
    SELECT CASE WHEN kind = 'payment' THEN -cents ELSE cents END AS c
    FROM events
    WHERE user_id = $1
  )a
)b;
      ''', [user._value or user]
    ]
  ).spread((hqres, oqres) ->
    response.send
      history: hqres.rows
      owe: oqres.rows[0].owe
  ).catch(next).finally(-> release())

module.exports = app
