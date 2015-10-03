Promise    = require 'lie'
Router     = require 'routerjs'
retry      = require 'retry'
tl         = require 'talio'
superagent = (require 'superagent-promise')((require 'superagent'), Promise)

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

if process.env.DEBUG
  process.env.API_URL = '//' + process.env.DOMAIN.replace /0$/, 1
  process.env.SITES_DOMAIN = process.env.DOMAIN.replace /0$/, '3'
  `
  Function.prototype.bind = function (oThis) {
    if (typeof this !== 'function') {
      // closest thing possible to the ECMAScript 5
      // internal IsCallable function
      throw new TypeError('Function.prototype.bind - what is trying to be bound is not callable');
    }

    var aArgs   = Array.prototype.slice.call(arguments, 1),
        fToBind = this,
        fNOP    = function() {},
        fBound  = function() {
          return fToBind.apply(this instanceof fNOP
                 ? this
                 : oThis,
                 aArgs.concat(Array.prototype.slice.call(arguments)));
        };

    fNOP.prototype = this.prototype;
    fBound.prototype = new fNOP();

    return fBound;
  };
  `
else
  process.env.API_URL = '//api.' + process.env.DOMAIN
  process.env.SITES_DOMAIN = process.env.DOMAIN

# landing page modifications
for node in document.querySelectorAll('[href$="#trello-login"]')
  node.href = process.env.API_URL + '/account/setup/start'

# humane.js notifications
humane.timeout = 2500
humane.waitForMove = false
humane.clickToClose = true
humane.info = humane.spawn(addnCls: 'humane-flatty-info', timeout: 5000)
humane.error = humane.spawn(addnCls: 'humane-flatty-error', timeout: 4000)
humane.success = humane.spawn(addnCls: 'humane-flatty-success', timeout: 2500)

router = new Router()

State = tl.StateFactory
  user: null
  boards: []
  setupDone:
    board: null
    ready: false
  history: []
  tab: 'create' # or ['manage', 'setupDone', 'plan']

handlers =
  refresh: (State, silent) ->
    Promise.resolve().then(->
      superagent
        .get(process.env.API_URL + '/account/info')
        .withCredentials()
        .type('json')
        .accept('json')
        .end()
    ).then((res) ->
      if res.body and res.body.user
        if location.pathname == '/'
          humane.log "You are logged in as <b>#{res.body.user}</b>. <b><a href=\"/account\">Click here</a></b> to go to your dashboard.", {timeout: 12000}
        else
          if State.get('user') != res.body.user
            console.log 'track'
            # amplitude.setUserId res.body.user
          State.change
            boards: res.body.boards
            activeboards: res.body.activeboards
            user: res.body.user
            premium: res.body.premium
          if not silent
            toURL = if res.body.activeboards.length then '#/' else '#/setup'
            if toURL != location.hash
              router.redirect toURL
      else
        if location.pathname == '/account/'
          location.href = process.env.API_URL + '/account/setup/start'
    ).catch(console.log.bind console)

  refreshHistory: (State) ->
    Promise.resolve().then(->
      superagent
        .get(process.env.API_URL + '/account/info/money')
        .withCredentials()
        .type('json')
        .accept('json')
        .end()
    ).then((res) ->
      State.change
        history: res.body.history
        owe: res.body.owe
    ).catch(console.log.bind console)

  setupBoard: (State, data) ->
    self = @
    # amplitude.logEvent 'setup', data
    Promise.resolve().then(->
      if data.name
        # create
        superagent
          .post(process.env.API_URL + '/board/setup')
          .send(name: data.name)
          .withCredentials()
          .end()
      else if data.id
        # reuse
        superagent
          .put(process.env.API_URL + '/board/setup')
          .send(id: data.id)
          .withCredentials()
          .end()
    ).then((res) ->
      board = res.body
      State.change
        setupDone:
          board: board
          ready: false
        tab: 'setupDone'

      # retry until the thing is working
      op = retry.operation
        retries: 100
        factor: 1.1
        minTimeout: 2000
        maxTimeout: 3300
      op.attempt (currentAttempt) ->
        Promise.resolve().then(->
          superagent
            .get("//#{board.subdomain}.#{process.env.SITES_DOMAIN}/")
            .end()
        ).then(->
          humane.success "Success!"
          self.refresh State, true
          State.change 'setupDone.ready', true
        ).catch(op.retry.bind op)
    ).catch(console.log.bind console)

  initialFetch: (State, data) ->
    # amplitude.logEvent 'initial-fetch', data
    Promise.resolve().then(->
      superagent
        .post(process.env.API_URL + '/board/' + data.id + '/initial-fetch')
        .withCredentials()
        .end()
    ).then(->
      humane.info "Successfully queued a <b>sync</b>."
    ).catch(->
      humane.error "An error ocurred"
    ).catch(console.log.bind console)

  deleteBoard: (State, data) ->
    self = @
    # amplitude.logEvent 'delete', data
    Promise.resolve().then(->
      superagent
        .del(process.env.API_URL + '/board/' + data.id)
        .withCredentials()
        .end()
    ).then(->
      humane.info "Board <b>#{data.id}</b> is not a site anymore."
      self.refresh State
    ).catch(->
      humane.error "Couldn't disable board <b>#{board.id}</b>."
      self.refresh State
    ).catch(console.log.bind console)

  changeSubdomain: (State, data) ->
    self = @
    # amplitude.logEvent 'subdomain', data
    Promise.resolve().then(->
      superagent
        .put(process.env.API_URL + '/board/' + data.id + '/subdomain')
        .send(value: data.subdomain)
        .withCredentials()
        .end()
    ).then(->
      humane.success "Changed subdomain to <b>#{data.subdomain}</b>. Board address is now <a href=\"//#{data.subdomain}.websitesfortrello.com\">http://#{data.subdomain}.websitesfortrello.com/</a>."
      self.refresh State
    ).catch(->
      humane.error "Couldn't change subdomain to <b>#{data.subdomain}</b>."
      self.refresh State
    ).catch(console.log.bind console)

  logout: (State) ->
    humane.log "Logging out..."
    Promise.resolve().then(->
      superagent
        .get(process.env.API_URL + '/account/logout')
        .withCredentials()
        .end()
    ).then(->
      location.pathname = '/'
    ).catch(console.log.bind console)

  togglePremium: (State, enable) ->
    Promise.resolve().then(->
      superagent
        .put(process.env.API_URL + '/account/premium')
        .send(enable: enable)
        .withCredentials()
        .end()
    ).then(->
      humane.success if enable then "You are now on the premium plan." else "You're not on the premium plan anymore."
      handlers.refresh State, true
      handlers.refreshHistory State
    ).catch(console.log.bind console)

  pay: (State, amount) ->
    Promise.resolve().then(->
      superagent
        .post(process.env.API_URL + '/account/billing/pay')
        .send(amount: amount)
        .withCredentials()
        .type('json')
        .accept('json')
        .end()
    ).then((res) ->
      location.href = res.body.url
    ).catch(console.log.bind console)

  paymentCompleted: (State, amount) ->
    Promise.resolve().then(->
      humane.success "You successfully paid <b>$#{amount}</b>."
      router.redirect '#/plan'
    ).catch(console.log.bind console)


if '/account/' != location.pathname
  # run this on landing page
  handlers.refresh State
else
  # setup router
  router
    .addRoute '#/setup', ->
      handlers.refresh State
      State.change 'tab', 'create'
    .addRoute '#/setup/again', ->
      handlers.refresh State
      State.change 'tab', 'create'
    .addRoute '#/plan', ->
      handlers.refresh State, true
      handlers.refreshHistory State
      State.change 'tab', 'plan'
    .addRoute '#/paid/:amount', (req) ->
      handlers.paymentCompleted State, req.params.amount
    .addRoute '#/logout', -> handlers.logout State
    .addRoute '#/', ->
      handlers.refresh State
      State.change 'tab', 'manage'
    .run('#/')

  app = document.createElement 'div'
  document.querySelector('body > .row').insertBefore(app, document.querySelector('body > .row > .container'))
  tl.run app, (require './vrender-main'), handlers, State
