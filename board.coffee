express       = require 'express'
Promise       = require 'bluebird'

{
  trello,
  pg,
  rabbitSend,
  superagent,
} = require './settings'
{
  userRequired
} = require './lib'

app = express()

setupBoard = (request, response, next) ->
  {id} = request.body
  trello.token = request.session.token

  release = null
  boardSetupPayload = JSON.stringify {
    'type': 'boardSetup'
    'board_id': id
    'username': request.session.user
    'user_token': request.session.token
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
    response.send board
  ).catch(next).finally(-> release())

app.post '/setup', userRequired, (request, response, next) ->
  {name} = request.body
  trello.token = request.session.token
  Promise.resolve().then(->
    trello.postAsync "/1/boards", {
      name: name
    }
  ).then((board) ->
    console.log ':: API :: created board', name
    request.body.id = board.id
    setupBoard request, response
  ).catch(next)
app.put '/setup', userRequired, setupBoard

app.get '/is-live/:subdomain', (request, response) ->
  Promise.resolve().then(->
    subdomain = request.params.subdomain
    superagent
      .head("http://#{subdomain}.#{process.env.SITES_DOMAIN}/")
      .end()
  ).then(->
    response.sendStatus 200
  ).catch((err) ->
    console.log err
    response.sendStatus 404
  )

app.put '/:boardId/subdomain', userRequired, (request, response, next) ->
  subdomain = request.body.value.toLowerCase()
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
                    ''', [subdomain, request.session.user, request.params.boardId]
  ).then(->
    response.sendStatus 200
  ).catch(next).finally(-> release())

app.post '/:boardId/initial-fetch', userRequired, (request, response, next) ->
  payload = JSON.stringify {
    'type': 'initialFetch'
    'board_id': request.params.boardId
  }
  rabbitSend(payload).then(-> response.sendStatus 202).catch(next)

app.delete '/:boardId', userRequired, (request, response, next) ->
  release = null

  payload = JSON.stringify {
    'type': 'boardDeleted'
    'board_id': request.params.boardId
    'user_token': request.session.token
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
                    ''', [request.session.user, request.params.boardId]
  ).then(->
    response.sendStatus 200

    rabbitSend payload
  ).catch(next).finally(-> release())


module.exports = app
