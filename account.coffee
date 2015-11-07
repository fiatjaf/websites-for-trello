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

app.get '/setup/start', (r, w) ->
  oauth.getRequestToken (err, data) ->
    return w.sendStatus 501 if err

    r.session.bag = data
    w.redirect data.redirect + '&scope=read,write,account&expiration=30days'

app.get '/setup/end', (r, w) ->
  return w.redirect process.env.SITE_URL if not r.session.bag
  bag = extend r.session.bag, r.query
  oauth.getAccessToken bag, (err, data) ->
    return w.redirect process.env.SITE_URL if err
    delete r.session.bag
    r.session.token = data.oauth_access_token
    trello.token = r.session.token
    trello.getAsync("/1/token/#{trello.token}/member/username")
    .then (v) ->
      r.session.user = v._value
      w.redirect process.env.SITE_URL + '/account'

app.get '/logout', (r, w) ->
  r.session = null
  if r.accepts('json', 'html') == 'json'
    w.sendStatus 200
  else
    w.redirect process.env.SITE_URL

app.use '/billing', require './billing'
app.use '/info', require './info'

module.exports = app
