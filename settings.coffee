pg             = require 'pg'
url            = require 'url'
paypal         = require 'paypal-rest-sdk'
Promise        = require 'bluebird'
NodeTrello     = require 'node-trello'
raygunProvider = require 'raygun'
superagent     = (require 'superagent-promise')((require 'superagent'), Promise)

if process.env.DEBUG
  process.env.SITE_URL = 'http://' + process.env.DOMAIN
  process.env.API_URL = 'http://' + process.env.DOMAIN.replace /0$/, 1
  process.env.SITES_DOMAIN = process.env.DOMAIN.replace /0$/, 3
  port = process.env.API_URL.split(':').slice(-1)[0]
else
  process.env.SITE_URL = 'https://' + process.env.DOMAIN
  process.env.API_URL = 'https://api.' + process.env.DOMAIN
  process.env.SITES_DOMAIN = process.env.DOMAIN
  port = process.env.PORT
  raygun = new raygunProvider.Client().init(apiKey: process.env.RAYGUN_API_KEY)
  raygun.user = (request) -> request.session.username

paypal.configure
  'mode': process.env.PAYPAL_MODE
  'client_id': process.env.PAYPAL_CLIENT_ID
  'client_secret': process.env.PAYPAL_CLIENT_SECRET

p = url.parse process.env.CLOUDAMQP_URL
rabbitMQPublishURL = "https://#{p.auth}@#{p.host}/api/exchanges#{p.pathname}/amq.default/publish"
rabbitSend = (message, opts={}) ->
  queue = switch opts.delayed
    when true then 'delay.4min'
    else 'wft'
  queue = if process.env.DEBUG then queue + '-test' else queue
  superagent
    .post(rabbitMQPublishURL)
    .set('Content-Type': 'application/json')
    .send(properties: {}, payload_encoding: 'string', routing_key: queue, payload: message)
    .end()
    .then((res) ->
      if not res.body.routed
        throw new Error('message not routed.')
      return res
    )
    .catch(console.log.bind console, ':: RECEIVE-WEBHOOKS :: rabbitSend error:')

trello = Promise.promisifyAll new NodeTrello process.env.TRELLO_API_KEY

Promise.promisifyAll paypal
Promise.promisifyAll paypal.payment

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

module.exports =
  pg: pg
  oauth: oauth
  trello: trello
  port: port
  raygun: raygun
  rabbitSend: rabbitSend
  paypal: paypal
  superagent: superagent
