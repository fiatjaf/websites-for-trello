Promise        = require 'bluebird'
express        = require 'express'
cookieSession  = require 'cookie-session'
bodyParser     = require 'body-parser'
cors           = require 'cors'

{ raygun, port } = require './settings'

app = express()
app.use bodyParser.json()
app.use bodyParser.urlencoded(extended: true)
app.use cookieSession
  secret: process.env.SESSION_SECRET or 'banana'
  name: 'wft'
  maxAge: 2505600000 # 29 days
  signed: true
CORS = cors
  origin: true
  credentials: true
app.use CORS
app.options '*', CORS

app.use '/account', require './account'
app.use '/board', require './board'

if raygun
  app.use (err, request, response, next) ->
    raygun.send err, {}, (->), request, ['API']
    next(err)

app.use (err, request, response) ->
  console.log ':: API :: error:', err
  console.log ':: API :: request:', request.originalUrl, request.body
  response.sendStatus 500

app.listen port, '0.0.0.0', ->
  console.log ':: API :: running at 0.0.0.0:' + port
