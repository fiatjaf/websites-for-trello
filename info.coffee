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
SELECT boards.id, boards.name, subdomain, "shortLink", users.plan AS plan
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE users.id = $1
ORDER BY boards.name
                      ''', [user._value or user])
    ]
  ).spread((username, boards, bqresult) ->
    request.session.user = username

    response.send
      user: username
      premium: bqresult.rows[0].plan == 'premium'
      boards: boards
      activeboards: bqresult.rows
  ).catch(next).finally(-> release())

module.exports = app
