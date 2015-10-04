express       = require 'express'
Promise       = require 'bluebird'
extend        = require 'xtend'

{
  trello,
  pg,
  oauth,
} = require './settings'
{
  userRequired
} = require './lib'

app = express()

app.get '/setup/start', (request, response) ->
  oauth.getRequestToken (err, data) ->
    return response.sendStatus 501 if err

    request.session.bag = data
    response.redirect data.redirect + '&scope=read,write,account&expiration=30days'

app.get '/setup/end', (request, response) ->
  return response.redirect process.env.SITE_URL if not request.session.bag
  bag = extend request.session.bag, request.query
  oauth.getAccessToken bag, (err, data) ->
    return response.redirect process.env.SITE_URL if err
    delete request.session.bag
    request.session.token = data.oauth_access_token
    response.redirect process.env.SITE_URL + '/account'

app.put '/premium', userRequired, (request, response, next) ->
  # let's just activate the premium features on this account
  # only later we will ask for the money.
  if not request.session.token
    return response.sendStatus 204

  user = null
  conn = null
  release = null
  Promise.resolve().then(->
    Promise.all [
      (request.session.user or trello.getAsync "/1/token/#{trello.token}/member/username")
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((u, db) ->
    user = u
    conn = db[0]
    release = db[1]

    switch request.body.enable
      when true
        conn.queryAsync '''
INSERT INTO events (user_id, kind, date, cents, data) VALUES
($1, 'plan', now(), NULL, $2),
($1, 'bill', now() + interval '1 millisecond', $3, $4)
        ''',
        [
          user._value or user
          {
            description: 'Premium plan enabled'
            plan: 'premium'
            enable: true
          }
          800
          {description: "Bill for the month starting in #{(new Date).toISOString().split('T')[0]}"}
        ]
      when false
        conn.queryAsync '''
INSERT INTO events (user_id, kind, date, data) VALUES ($1, 'plan', now(), $2)
        ''',
        [
          user._value or user
          {
            description: 'Premium plan disabled'
            plan: 'premium'
            enable: false
          }
        ]
  ).then(-> response.send ok: true).catch(next).finally(-> release())

app.get '/logout', (request, response) ->
  request.session = null
  if request.accepts('json', 'html') == 'json'
    response.sendStatus 200
  else
    response.redirect process.env.SITE_URL

app.use '/billing', require './billing'
app.use '/info', require './info'

module.exports = app
