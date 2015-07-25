pg            = require 'pg'
redis         = require 'rsmq/node_modules/redis'
RedisSMQ      = require 'rsmq'
Promise       = require 'bluebird'
NodeTrello    = require 'node-trello'
extend        = require 'xtend'
raygunProvider= require 'raygun'
express       = require 'express'
cookieSession = require 'cookie-session'
bodyParser    = require 'body-parser'
cors          = require 'cors'

if process.env.DEBUG
  process.env.SITE_URL = 'http://' + process.env.DOMAIN
  process.env.API_URL = 'http://' + process.env.DOMAIN.replace /0$/, 1
  process.env.WEBHOOK_URL = 'http://' + process.env.DOMAIN.replace /0$/, 2
  port = process.env.API_URL.split(':').slice(-1)[0]
  rsmq_ns = 'test-rsmq'
else
  process.env.SITE_URL = 'http://' + process.env.DOMAIN
  process.env.API_URL = 'http://api.' + process.env.DOMAIN
  process.env.WEBHOOK_URL = 'http://webhooks.' + process.env.DOMAIN
  port = process.env.PORT
  rsmq_ns = 'rsmq'
  raygun = new raygunProvider.Client().init(apiKey: process.env.RAYGUN_API_KEY)
  raygun.user = (request) -> request.session.username

r = redis.createClient process.env.REDIS_PORT, process.env.REDIS_HOST, {
  auth_pass: process.env.REDIS_PASSWORD
  enable_offline_queue: false
}
qname = 'webhooks'
rsmq = new RedisSMQ
  client: r
  ns: rsmq_ns
rsmq.sendMessageAsync = Promise.promisify rsmq.sendMessage

trello = Promise.promisifyAll new NodeTrello process.env.TRELLO_API_KEY
oauth = new NodeTrello.OAuth(
  process.env.TRELLO_API_KEY
  process.env.TRELLO_API_SECRET
  process.env.API_URL + '/account/setup/end'
  'Websites for Trello'
)
pg.defaults.poolSize = 2
pg.defaults.ssl = true
Promise.promisifyAll pg.Client.prototype
Promise.promisifyAll pg.Client
Promise.promisifyAll pg.Connection.prototype
Promise.promisifyAll pg.Connection
Promise.promisifyAll pg.Query.prototype
Promise.promisifyAll pg.Query
Promise.promisifyAll pg

app = express()
app.use bodyParser.json()
app.use bodyParser.urlencoded(extended: true)
app.use cookieSession
  secret: process.env.SESSION_SECRET or 'banana'
  name: 'wft'
  maxAge: 2505600000 # 29 days
  signed: true
CORS = cors
  origin: process.env.SITE_URL
  credentials: true
app.use CORS
app.options '*', CORS

userRequired = (request, response, next) ->
  if not request.session.user
    return response.sendStatus 401
  next()

app.get '/account/setup/start', (request, response) ->
  oauth.getRequestToken (err, data) ->
    return response.sendStatus 501 if err

    request.session.bag = data
    response.redirect data.redirect + '&scope=read,write,account&expiration=30days'

app.get '/account/setup/end', (request, response) ->
  return response.redirect process.env.SITE_URL if not request.session.bag
  bag = extend request.session.bag, request.query
  oauth.getAccessToken bag, (err, data) ->
    return response.redirect process.env.SITE_URL if err
    delete request.session.bag
    request.session.token = data.oauth_access_token
    response.redirect process.env.SITE_URL + '/account'

app.get '/account/info', (request, response, next) ->
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
                      ''', [user._value or user])
    ]
  ).spread((username, boards, qresult) ->
    request.session.user = username

    response.send
      user: username
      boards: boards
      activeboards: qresult.rows
  ).catch(next)
  .finally(->
    release()
  )

app.get '/account/logout', (request, response) ->
  request.session = null
  if request.accepts('json', 'html') == 'json'
    response.sendStatus 200
  else
    response.redirect process.env.SITE_URL

setupBoard = (request, response, next) ->
  {id} = request.body
  trello.token = request.session.token
  release = null

  payload = JSON.stringify {
    'type': 'boardSetup'
    'board_id': id
    'username': request.session.user
    'user_token': request.session.token
  }
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).then((db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      rsmq.sendMessageAsync { qname: qname, message: payload }
      conn.queryAsync 'SELECT id, name, "shortLink", subdomain FROM boards WHERE id=$1', [id]
      trello.getAsync "/1/boards/#{id}/shortLink"
    ]
  ).spread((_, qresult, shortLink) ->
    console.log ':: API :: boardSetup message sent:', payload
    if qresult.rows.length
      board = qresult.rows[0]
    else
      board =
        id: id
        shortLink: shortLink._value
        subdomain: shortLink._value.toLowerCase()
    response.send board
  ).catch(next)
  .finally(->
    release()
  )

app.post '/board/setup', userRequired, (request, response, next) ->
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
app.put '/board/setup', userRequired, setupBoard

app.put '/board/:boardId/subdomain', userRequired, (request, response, next) ->
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
  ).catch(next)
  .finally(->
    release()
  )

app.delete '/board/:boardId', userRequired, (request, response, next) ->
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

    rsmq.sendMessageAsync { qname: qname, message: payload }
  ).catch(next)
  .finally(->
    release()
  )

if raygun
  app.use (err, request, response, next) ->
    raygun.send err, {}, (->), request, ['API']
    next(err)

app.use (err, request, response) ->
  response.sendStatus 500
  console.log ':: API :: error:', err
  console.log ':: API :: request:', request.originalUrl, request.body

app.listen port, '0.0.0.0', ->
  console.log ':: API :: running at 0.0.0.0:' + port
