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

app.get '/info', (request, response, next) ->
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
ORDER BY boards.name
                      ''', [user._value or user])
      conn.queryAsync('''
SELECT premium
FROM users
WHERE users.id = $1
                      ''', [user._value or user])
    ]
  ).spread((username, boards, bqresult, pqresult) ->
    request.session.user = username

    response.send
      user: username
      premium: pqresult.rows[0].premium
      boards: boards
      activeboards: bqresult.rows
  ).catch(next).finally(-> release())

app.get '/info/money', userRequired, (request, response, next) ->
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
      conn.queryAsync '''
SELECT
  to_char(date, 'TMMonth DD, YYYY') AS date,
  kind,
  '$' || left(cents, -2) || '.' || right(cents, -1) AS amount,
  data->>'description' AS description
FROM (
  SELECT date, kind, lpad(cents::text, 3, '0') AS cents, data
  FROM events
  WHERE user_id = $1
  ORDER BY date DESC
)a
      ''', [user._value or user]
      conn.queryAsync '''
SELECT '$' || left(cents::text, -2) || '.' || right(cents::text, -1) AS owe
FROM (
  SELECT lpad(sum(c)::text, 3, '0') AS cents FROM (
    SELECT CASE WHEN kind = 'payment' THEN -cents ELSE cents END AS c
    FROM events
    WHERE user_id = $1
  )a
)b;
      ''', [user._value or user]
    ]
  ).spread((hqres, oqres) ->
    response.send
      history: hqres.rows
      owe: oqres.rows[0].owe
  ).catch(next).finally(-> release())

app.put '/premium', userRequired, (request, response, next) ->
  # let's just activate the premium features on this account
  # only later we will ask for the money.
  if not request.session.token
    return response.sendStatus 204

  release = null
  Promise.resolve().then(->
    Promise.all [
      (request.session.user or trello.getAsync "/1/token/#{trello.token}/member/username")
      pg.connectAsync process.env.DATABASE_URL
    ]
  ).spread((user, db) ->
    conn = db[0]
    release = db[1]

    enable = request.body.enable

    updateEvents = switch enable
      when true then [
        '''
INSERT INTO events (user_id, kind, date, cents, data) VALUES
($1, 'plan', now(), NULL, $2),
($1, 'bill', now(), $3, $4)
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
      ]
      when false then [
        '''
INSERT INTO events (user_id, kind, date, data) VALUES
($1, 'plan', now(), $2)
        ''',
        [
          user._value or user
          {
            description: 'Premium plan disabled'
            plan: 'premium'
            enable: false
          }
        ]
      ]

    conn.queryAsync('''
UPDATE users
SET premium = $2
WHERE users.id = $1
    ''', [user._value or user, enable])
    conn.queryAsync updateEvents[0], updateEvents[1]
  ).then((qresult) ->
    response.send
      ok: true
  ).catch(next).finally(-> release())

app.get '/logout', (request, response) ->
  request.session = null
  if request.accepts('json', 'html') == 'json'
    response.sendStatus 200
  else
    response.redirect process.env.SITE_URL

app.use '/billing', require './billing'

module.exports = app
