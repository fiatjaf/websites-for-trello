pg            = require 'pg'
redis         = require 'rsmq/node_modules/redis'
RedisSMQ      = require 'rsmq'
Promise       = require 'bluebird'
NodeTrello    = require 'node-trello'
extend        = require 'xtend'
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
  process.env.API_URL = 'http://api' + process.env.DOMAIN
  process.env.WEBHOOK_URL = 'http://webhooks' + process.env.DOMAIN
  port = process.env.PORT
  rsmq_ns = 'rsmq'

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

handleError = (request, response, e) ->
  response.sendStatus 500
  console.log ':: API :: error:', e
  console.log ':: API :: request:', request.originalUrl, request.body

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

app.get '/account', (request, response) ->
  if not request.session.token
    return response.sendStatus 204

  trello.token = request.session.token
  release = null

  Promise.resolve().then(->
    Promise.all [
      if request.session.username then request.session.username else trello.getAsync "/1/token/#{trello.token}/member/username"
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((user, db) ->
    conn = db[0]
    release = db[1]

    Promise.all [
      user._value
      trello.getAsync "/1/members/#{user._value}/boards", {filter: 'open'}
      conn.queryAsync('''
SELECT boards.id, boards.name, boards.subdomain
FROM boards
INNER JOIN users ON users.id = boards.user_id
WHERE users.id = $1
                      ''', [user._value])
    ]
  ).spread((username, boards, qresult) ->
    request.session.user = username

    response.send
      user: username
      boards: boards
      activeboards: qresult.rows
  ).catch(handleError.bind(@, request, response))
  .finally(release)

app.get '/account/logout', (request, response) ->
  delete request.session.token
  delete request.session.user
  response.redirect process.env.SITE_URL

app.post '/board/setup', userRequired, (request, response) ->
  {name} = request.body
  payload = JSON.stringify {
    'type': 'boardCreateAndSetup'
    'board_name': name
    'username': request.session.user
    'user_token': request.session.token
  }
  Promise.resolve().then(->
    rsmq.sendMessageAsync
      qname: qname
      message: payload
  ).then((data) ->
    console.log ':: API :: boardCreateAndSetup message sent:', payload
    response.sendStatus 201
  ).catch(handleError.bind(@, request, response))

app.put '/board/setup', userRequired, (request, response) ->
  {id} = request.body
  payload = JSON.stringify {
    'type': 'boardSetup'
    'board_id': id
    'username': request.session.user
    'user_token': request.session.token
  }
  Promise.resolve().then(->
    rsmq.sendMessageAsync
      qname: qname
      message: payload
  ).then((data) ->
    console.log ':: API :: boardSetup message sent:', payload
    response.sendStatus 200
  ).catch(handleError.bind(@, request, response))

app.put '/board/:boardId/subdomain', userRequired, (request, response) ->
  {subdomain} = request.body
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).spread((conn, release) ->
    conn.queryAsync '''
UPDATE boards
SET subdomain = $1
WHERE user_id = $2
  AND id = $3
                    ''', [subdomain, request.session.user, request.params.boardId]
  ).then(->
    response.sendStatus 200
  ).catch(handleError.bind(@, request, response))
  .finally(release)

app.delete '/board/:boardId', userRequired, (request, response) ->
  Promise.resolve().then(->
    pg.connectAsync process.env.DATABASE_URL
  ).spread((conn, release) ->
    conn.queryAsync '''
DELETE FROM boards
WHERE user_id = $1
  AND id = $2
                    ''', [request.session.user, request.params.boardId]
  ).then(->
    response.sendStatus 200
  ).catch(handleError.bind(@, request, response))
  .finally(release)

app.listen port, '0.0.0.0', ->
  console.log ':: API :: running at 0.0.0.0:' + port
