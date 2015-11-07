express       = require 'express'
Promise       = require 'bluebird'

{ trello, pg, rabbitSend, superagent, } = require './settings'
{ userRequired } = require './lib'

app = express()

setupBoard = (r, w) ->
  {id} = r.body
  trello.token = r.session.token

  release = null
  boardSetupPayload = JSON.stringify {
    'type': 'boardSetup'
    'board_id': id
    'username': r.session.user
    'user_token': r.session.token
  }
  initialFetchPayload = JSON.stringify {
    'type': 'initialFetch'
    'board_id': id
  }
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      conn.queryAsync 'SELECT id, name, "shortLink", subdomain FROM boards WHERE id=$1', [id]
      trello.getAsync "/1/boards/#{id}/shortLink"
      rabbitSend boardSetupPayload
      rabbitSend initialFetchPayload, delayed: true
    ]
  ).spread((qresult, shortLink) ->
    console.log ':: API :: boardSetup message sent:', boardSetupPayload
    if qresult.rows.length
      board = qresult.rows[0]
    else
      board =
        id: id
        shortLink: shortLink._value
        subdomain: shortLink._value.toLowerCase()
    w.send board
  ).finally(-> release())

app.post '/setup', userRequired, (r, w) ->
  {name} = r.body
  trello.token = r.session.token
  Promise.resolve().then(->
    trello.postAsync "/1/boards", {
      name: name
    }
  ).then((board) ->
    console.log ':: API :: created board', name
    r.body.id = board.id
    setupBoard r, w
  )
app.put '/setup', userRequired, setupBoard

app.get '/is-live/:subdomain', (r, w) ->
  Promise.resolve().then(->
    subdomain = r.params.subdomain
    superagent
      .head("http://#{subdomain}.#{process.env.SITES_DOMAIN}/")
      .end()
  ).then(->
    w.sendStatus 200
  ).catch((err) ->
    console.log err
    w.sendStatus 404
  )

app.put '/:boardId/subdomain', userRequired, (r, w) ->
  subdomain = r.body.value.toLowerCase()
  release = null

  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((db) ->
    conn = db[0]
    release = db[1]

    conn.queryAsync '''
UPDATE boards
SET subdomain = (CASE
  WHEN NOT EXISTS (SELECT id FROM boards WHERE subdomain = $1) THEN $1
  ELSE (SELECT subdomain FROM boards WHERE id = $2)
  END)
WHERE user_id = $2
AND id = $3
    ''', [subdomain, r.session.user, r.params.boardId]
  ).then(->
    w.sendStatus 200
  ).finally(-> release())

app.post '/:boardId/initial-fetch', userRequired, (r, w) ->
  payload = JSON.stringify {
    'type': 'initialFetch'
    'board_id': r.params.boardId
  }
  rabbitSend(payload).then(-> w.sendStatus 202)

app.delete '/:boardId', userRequired, (r, w) ->
  release = null

  payload = JSON.stringify {
    'type': 'boardDeleted'
    'board_id': r.params.boardId
    'user_token': r.session.token
  }
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((db) ->
    conn = db[0]
    release = db[1]

    conn.queryAsync '''
DELETE FROM boards
WHERE user_id = $1
  AND id = $2
    ''', [r.session.user, r.params.boardId]
  ).then(->
    w.sendStatus 200

    rabbitSend payload
  ).finally(-> release())

module.exports = app
