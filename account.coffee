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
  enable = request.body.enable
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

    switch enable
      when true
        Promise.resolve().then(->
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
        )
      when false
        Promise.resolve().then(->
          conn.queryAsync '''
SELECT *
FROM events
WHERE user_id = $1
ORDER BY date DESC
LIMIT 2
          ''', [user._value or user]
        ).then((qres) ->
          history =
          if qres.rows.length == 2 and qres.rows[1].kind == 'plan' and qres.rows[0].kind == 'bill'
            if qres.rows[1].date.toISOString.split('T')[0] == (new Date).toISOString().split('T')[0] and qres.rows[1].data.enable == true
              # if the two last entries were made today and by pressing the
              # 'enable premium' button, we remove them instead of creating a new
              # 'disable' event.
              conn.queryAsync '''
DELETE FROM events WHERE id = $1 OR id = $2
              ''', [qres.rows[0].id, qres.rows[1].id]
            else
              # if, however, they were created yesterday or before, we just
              # change the value of the bill to reflect the proportion of days
              conn.queryAsync '''
BEGIN;
UPDATE events SET cents = ($2/31)*(now()::date - date::date) WHERE id = $1;
INSERT INTO events (user_id, kind, date, data) VALUES ($3, 'plan', now(), $4)
COMMIT;
              ''',
              [
                qres.rows[0].id
                800
                user._value or user
                {
                  description: 'Premium plan disabled'
                  plan: 'premium'
                  enable: false
                }
              ]
          else
            # if the person cancels after a month (after he has more than
            # one sequential bills or interspersed payments or other event)
            # just cancel the plan and ignore the other effects.
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
        )
  ).then(->
    # finally remove the premium status of the user's account
    conn.queryAsync('''
UPDATE users
SET premium = $2
WHERE users.id = $1
    ''', [user._value or user, enable])
  ).then((qresult) -> response.send ok: true).catch(next).finally(-> release())

app.get '/logout', (request, response) ->
  request.session = null
  if request.accepts('json', 'html') == 'json'
    response.sendStatus 200
  else
    response.redirect process.env.SITE_URL

app.use '/billing', require './billing'
app.use '/info', require './info'

module.exports = app
