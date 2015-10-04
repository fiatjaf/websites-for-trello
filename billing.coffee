url           = require 'url'
qs            = require 'qs'
express       = require 'express'
Promise       = require 'bluebird'

{
  pg,
  paypal,
} = require './settings'
{
  userRequired
} = require './lib'

app = express()

app.post '/pay', userRequired, (request, response, next) ->
  request.session.amount = request.body.amount

  Promise.resolve().then(->
    paypal.payment.createAsync
      intent: 'sale'
      payer: {
        payment_method: 'paypal'
      }
      redirect_urls: {
          return_url: process.env.API_URL + '/account/billing/pay/callback'
          cancel_url: process.env.API_URL + '/account/billing/pay/cancel'
      }
      transactions: [{
        description: '1 month worth of Websites for Trello'
        soft_descriptor: 'Websites for Trello'
        amount: {
          currency: 'USD'
          total: request.session.amount
        }
      }]
  ).then((payment) ->
    redirect = process.env.API_URL + '/account/billing/pay/cancel'

    if payment.state == 'created'
      for link in payment.links
        if link.rel == 'approval_url'
          redirect = link.href
          break

    if 'json' == request.accepts 'json'
      response.send {url: redirect}
    else
      response.redirect redirect
  ).catch(next)

app.get '/pay/callback', userRequired, (request, response, next) ->
  q = qs.parse(url.parse(request.url).search.slice(1))
  paymentId = q['paymentId']
  payerId = q['PayerID']

  release = null
  Promise.resolve().then(->
    paypal.payment.executeAsync paymentId,
      payer_id: payerId
      transactions: [{
        description: '1 month worth of Websites for Trello'
        soft_descriptor: 'Websites for Trello'
        amount: {
          currency: 'USD'
          total: request.session.amount
        }
      }]
  ).then((payment) ->
    request.session.amount = null # just cleaning

    if payment.state != 'approved'
      return response.redirect process.env.API_URL + '/account/billing/pay/cancel'

    response.redirect process.env.SITE_URL + '/account/#/paid'

    # save payment as event
    Promise.all [
      payment
      (request.session.user or trello.getAsync "/1/token/#{trello.token}/member/username")
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((payment, user, db) ->
    conn = db[0]
    release = db[1]

    conn.queryAsync '''
INSERT INTO events (user_id, kind, date, cents, data)
VALUES ($1, 'payment', $2, now(), $3)
    ''', [
      user._value or user
      payment.transactions.map((t) -> parseInt t.amount.total.replace('.', '')).reduce(((a, b) -> a + b), 0)
      {
        description: 'Paypal'
        transactions: payment.transactions
        payer: payment.payer
      }
    ]
  ).then(release).catch(next)

app.get '/pay/cancel', userRequired, (request, response, next) ->
  response.send 'We couldn\'t complete your payment.'

module.exports = app
