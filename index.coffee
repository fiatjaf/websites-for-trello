pg            = require 'pg'
AWS           = require 'aws-sdk'
Promise       = require 'bluebird'
NodeTrello    = require 'node-trello'
extend        = require 'xtend'
express       = require 'express'
cookieSession = require 'cookie-session'
bodyParser    = require 'body-parser'
cors          = require 'cors'

trello = Promise.promisifyAll new NodeTrello process.env.TRELLO_API_KEY
oauth = new Trello.OAuth(
  process.env.TRELLO_API_KEY
  process.env.TRELLO_API_SECRET
  process.env.SITE_URL + '/setup/board'
  'Websites for Trello'
)
pg.defaults.poolSize = 2
Promise.promisifyAll pg.Client.prototype
Promise.promisifyAll pg.Client
Promise.promisifyAll pg.Connection.prototype
Promise.promisifyAll pg.Connection
Promise.promisifyAll pg.Query.prototype
Promise.promisifyAll pg.Query
Promise.promisifyAll pg

sqs = new AWS.SQS
  region: 'us-east-1'
sqs.sendMessageAsync = Promise.promisify sqs.sendMessage

app = express()
app.use bodyParser.json()
app.use bodyParser.urlencoded(extended: true)
app.use cookieSession
  path: '/session'
  secret: process.env.SESSION_SECRET or 'banana'
  name: 'wft'
  maxAge: 36000000000 # 1000h
  signed: true
CORS = cors
  origin: process.env.SITE_URL
  credentials: true
app.use CORS
app.options '*', CORS

app.post '/account/setup/start', (request, response) ->
  oauth.getRequestToken (err, data) ->
    if err
      response.sendStatus 501

    data.redirect + '&scope=read,write,account'
    if request.query.next
      data.redirect + '&next=' + request.query.next

    request.session.bag = data
    response.redirect data.redirect

app.get '/account/setup/end', (request, response) ->
  if not request.session.bag
    return response.redirect request.query.next or process.env.SITE_URL

  bag = extend request.session.bag, request.query
  oauth.getAccessToken bag, (err, data) ->
    if err
      return response.redirect request.query.next or process.env.SITE_URL
    delete request.session.bag
    request.session.token = data.oauth_token
    response.redirect process.env.SITE_URL + '/account'

app.get '/account', (request, response) ->
  if not request.session.token
    return response.send {user: null}
  trello.token = request.session.token
  release = null

  Promise.resolve().then(->
    Promise.all [
      trello.get "/1/token/#{request.session.token}/member/username"
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((username, db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      username
      trello.get "/1/members/#{username}/boards/open"
      conn.queryAsync('''
SELECT id, name, subdomain
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE users.id = $1
                      ''', [username])
    ]
  ).spread((username, boards, qresult) ->
    request.session.user = username

    response.send
      user: username
      boards: boards
      activeboards: qresult.rows
  ).catch((e) ->
    response.sendStatus 500
    console.log e
  ).finally(release)

app.get '/account/logout', (request, response) ->
  delete request.session.token
  delete request.session.user
  response.redirect process.env.SITE_URL

userRequired = (request, response, next) ->
  if not request.session.user
    return response.sendStatus 401
  next()

app.post '/board/setup', userRequired, (request, response) ->
  {name} = request.body
  Promise.resolve().then(->
    sqs.sendMessageAsync
      MessageBody: JSON.stringify {
        'type': 'boardCreateAndSetup'
        'board_name': name
        'user_token': request.session.token
      }
      QueueUrl: process.env.SQS_URL
      DelaySeconds: 0
  ).then((data) ->
    console.log 'boardCreateAndSetup message sent', data
    response.sendStatus 201
  ).catch((e) ->
    response.sendStatus 500
    console.log e
  )

app.put '/board/setup', userRequired, (request, response) ->
  {id} = request.body
  Promise.resolve().then(->
    sqs.sendMessageAsync
      MessageBody: JSON.stringify {
        'type': 'boardSetup'
        'board_id': id
        'user_token': request.session.token
      }
      QueueUrl: process.env.SQS_URL
      DelaySeconds: 0
  ).then((data) ->
    console.log 'boardSetup message sent', data
    response.sendStatus 200
  ).catch((e) ->
    response.sendStatus 500
    console.log e
  )

app.put '/board/:boardId/subdomain', userRequired, (request, response) ->
  {subdomain} = request.body
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((conn) ->
    conn.queryAsync '''
UPDATE boards
SET subdomain = $1
WHERE user_id = $2
  AND id = $3
                    ''', [subdomain, request.session.user, request.params.boardId]
  ).then(->
    response.sendStatus 200
  ).catch((e) ->
    response.sendStatus 500
    console.log e
  )

app.delete '/board/:boardId', userRequired, (request, response) ->
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((conn) ->
    conn.queryAsync '''
DELETE FROM boards
WHERE user_id = $1
  AND id = $2
                    ''', [request.session.user, request.params.boardId]
  ).then(->
    response.sendStatus 200
  ).catch((e) ->
    response.sendStatus 500
    console.log e
  )

port = process.env.PORT or 5000
app.listen port, '0.0.0.0', ->
  console.log 'running at 0.0.0.0:' + port
