express       = require 'express'
Promise       = require 'bluebird'

{ raygun, pg, paypal, trello } = require './settings'
{ userRequired } = require './lib'

app = express()

app.post '/premium', userRequired, (r, w) ->
  release = null
  conn = null

  # setting up premium account
  if r.body.enable
    # first we ask for the money
    paypal.authenticate
      RETURNURL: process.env.API_URL + '/account/billing/callback/success'
      CANCELURL: process.env.API_URL + '/account/billing/callback/fail'
      PAYMENTREQUEST_0_AMT: 17
      L_BILLINGAGREEMENTDESCRIPTION0: "Websites for Trello premium account (user ##{r.session.userid})"
      BRANDNAME: 'Websites for Trello'
      BUYEREMAILOPTINENABLE: 0
    ,
      (err, data, url) ->
        if not err
          if 'json' == r.accepts 'json'
            w.send {url: url}
          else
            w.redirect url
        else
          raygun.send err, {}, (->), r
          console.log ':: API :: paypal authentication error', err.stack or err, data

  # cancelling premium account
  else
    Promise.resolve().then(->
      pg.connectAsync process.env.DATABASE_URL
    ).then((db) ->
      conn = db[0]
      release = db[1]
      conn.queryAsync 'SELECT "paypalProfileId" FROM users WHERE _id = $1', [r.session.userid]
    ).then((res) ->
      paypalProfileId = res.rows[0].paypalProfileId
      if paypalProfileId
        Promise.fromNode(paypal.modifySubscription.bind(
            paypal,
            paypalProfileId,
            'Cancel',
            "Account downgraded from API on #{(new Date).toISOString()}"
        ))
    ).then(->
      conn.queryAsync '''UPDATE users SET plan = null, "paypalProfileId" = null WHERE _id = $1'''
      , [r.session.userid]
    ).then(->
      w.status(200).send()
    ).finally(-> release())

app.get '/callback/success', userRequired, (r, w) ->
  # first we verify the subscription
  {token, PayerID} = r.query
  trello.token = r.session.token

  paypal.createSubscription token, PayerID,
    AMT: 17
    DESC: "Websites for Trello premium account (user ##{r.session.userid})"
    BILLINGPERIOD: 'Month'
    BILLINGFREQUENCY: 1
    MAXFAILEDPAYMENTS: 3
    AUTOBILLOUTAMT: 'AddToNextBilling'
  , (err, data) ->
    if err
      raygun.send err, {}, (->), r
      w.redirect process.env.API_URL + '/account/billing/callback/fail'
      return

    # now we activate the premium features on this account
    if not r.session.token
      return w.status(204).send()

    conn = null
    release = null
    Promise.resolve().then(->
      pg.connectAsync process.env.DATABASE_URL
    ).then((db) ->
      conn = db[0]
      release = db[1]

      conn.queryAsync '''
UPDATE users SET plan = 'premium', "paypalProfileId" = $1 WHERE _id = $2
      ''', [data.PROFILEID, r.session.userid]
    ).then(->
      w.redirect process.env.SITE_URL + '/account/#/upgrade/success'
    ).finally(-> release())

app.get '/callback/fail', userRequired, (r, w) ->
  w.send 'We couldn\'t complete your payment. Please message us on <b>websitesfortrello@boardthreads.com</b>'

module.exports = app
