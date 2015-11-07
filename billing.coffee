express       = require 'express'
Promise       = require 'bluebird'

{ raygun, pg, paypal } = require './settings'
{ userRequired } = require './lib'

app = express()

app.put '/premium', userRequired, (r, w) ->
  # first we ask for the money
  paypal.authenticate
    RETURNURL: process.env.API_URL + '/account/billing/callback/success'
    CANCELURL: process.env.API_URL + '/account/billing/callback/fail'
    PAYMENTREQUEST_0_AMT: 8
    L_BILLINGAGREEMENTDESCRIPTION0: "Websites for Trello premium account"
    BRANDNAME: 'Websites for Trello'
    BUYEREMAILOPTINENABLE: 0
  ,
    (err, data, url) ->
      if not err
        if 'json' == r.accepts 'json'
          w.send {url: redirect}
        else
          w.redirect redirect
      else
        raygun.send err, {}, (->), r
        console.log err, data

app.get '/callback/success', userRequired, (r, w) ->
  # first we verify the subscription
  {token, PayerID} = r.query
  trello.token = r.session.token

  paypal.createSubscription token, PayerID,
    AMT: 10
    DESC: "Websites for Trello premium account"
    BILLINGPERIOD: 'Month'
    BILLINGFREQUENCY: 12
    MAXFAILEDPAYMENTS: 3
    AUTOBILLOUTAMT: 'AddToNextBilling'
  , (err, data) ->
    if err
      raygun.send err, {}, (->), r
      w.redirect process.env.API_URL + '/account/billing/callback/fail'
      return

    # now we activate the premium features on this account
    if not r.session.token
      return w.sendStatus 204

    user = null
    conn = null
    release = null
    Promise.resolve().then(->
      Promise.all [
        r.session.user
        pg.connectAsync process.env.DATABASE_URL
      ]
    ).spread((u, db) ->
      user = u
      conn = db[0]
      release = db[1]

      plan = if r.body.enable then 'premium' else null
      conn.queryAsync '''
UPDATE users SET plan = $1, "paypalProfileId" = $2 WHERE id = $3
      ''', [plan, data.PROFILEID, user]
    ).then(->
      w.redirect process.env.SITE_URL + '/account/#upgrade/success'
    ).finally(-> release())

app.get '/callback/fail', userRequired, (r, w) ->
  w.send 'We couldn\'t complete your payment. Please message us on <b>websitesfortrello@boardthreads.com</b>'

module.exports = app
