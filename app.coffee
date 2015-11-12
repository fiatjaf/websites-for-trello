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
  firstRefresh: true

handlers =
  refresh: (State) ->
    Promise.resolve().then(->
      superagent
        .get(process.env.API_URL + '/account/info')
        .withCredentials()
        .type('json')
        .accept('json')
        .end()
    ).then((res) ->
      if res.body and res.body.user
        unless location.pathname.match /\/account\//
          humane.log "You are logged in as <b>#{res.body.user}</b>. <b><a href=\"/account\">Click here</a></b> to go to your dashboard.", {timeout: 12000}
        else
          if State.get('user') != res.body.user
            ga 'send', 'event', 'user', 'login', res.body.user
            ga 'set', 'userId', res.body.user
          State.change
            boards: res.body.boards
            activeboards: res.body.activeboards
            user: res.body.user
            premium: res.body.premium
          if State.get('firstRefresh') and (location.hash == '#/' or location.hash == '#/setup')
            toURL = if res.body.activeboards.length then '#/' else '#/setup'
            if toURL != location.hash
              router.redirect toURL
      else
        if location.pathname == '/account/'
          location.href = process.env.API_URL + '/account/setup/start'

      State.silentlyUpdate 'firstRefresh', false
    ).catch(console.log.bind console)

  setupBoard: (State, data) ->
    self = @
    Promise.resolve().then(->
      if data.name
        ga 'send', 'event', 'board', 'create', data.name
        # create
        superagent
          .post(process.env.API_URL + '/board/setup')
          .send(name: data.name)
          .withCredentials()
          .end()
      else if data.id
        ga 'send', 'event', 'board', 'reuse', data.id
        # reuse
        superagent
          .put(process.env.API_URL + '/board/setup')
          .send(id: data.id)
          .withCredentials()
          .end()
    ).then((res) ->
      board = res.body
      ga 'send', 'event', 'board', 'setup-done', board.id

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
            .get(process.env.API_URL + '/board/is-live/' + board.subdomain)
            .end()
        ).then(->
          self.refresh State
          ga 'send', 'event', 'board', 'setup-success', board.id
          humane.success "Success!"
          State.change 'setupDone.ready', true
        ).catch(op.retry.bind op)
    ).catch(console.log.bind console)

  initialFetch: (State, data) ->
    ga 'send', 'event', 'board', 'initial-fetch', data.id
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
    ga 'send', 'event', 'board', 'delete', data.id
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
    ga 'send', 'event', 'board', 'subdomain', data.id
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
    ga 'send', 'event', 'user', 'logout', State.get('user')
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
    if enable == false and not confirm 'Really disable the premium plan?'
      return

    Promise.resolve().then(->
      if enable == true
        ga 'send', 'event', 'billing', 'enable', 'premiumn'
      else if enable == false
        ga 'send', 'event', 'billing', 'disable', 'premium'
      superagent
        .post(process.env.API_URL + '/account/billing/premium')
        .send(enable: enable)
        .withCredentials()
        .end()
    ).then((res) ->
      if enable == true
        location.href = res.body.url
      else if enable == false
        humane.info "You're not on the premium plan anymore."
        handlers.refresh State
    ).catch(console.log.bind console)

  premiumSuccess: (State) ->
    ga 'send', 'event', 'billing', 'success', 'premium'
    Promise.resolve().then(->
      humane.success "You are now on the premium plan!"
      router.redirect '#/plan'
    ).catch(console.log.bind console)

if '/account/' != location.pathname.slice(0, 9)
  # run this on landing page
  handlers.refresh State
else
  # setup router
  handlers.refresh State
  router
    .addRoute '#/setup', ->
      State.change 'tab', 'create'
    .addRoute '#/setup/again', ->
      State.change 'tab', 'create'
    .addRoute '#/plan', ->
      State.change 'tab', 'plan'
    .addRoute '#/upgrade/success', ->
      handlers.premiumSuccess State
    .addRoute '#/logout', -> handlers.logout State
    .addRoute '#/', ->
      State.change 'tab', 'manage'
    .errors 404, ->
      router.redirect '#/'
    .run(location.hash)

  app = document.createElement 'div'
  document.querySelector('body > .row').insertBefore(app, document.querySelector('body > .row > .container'))
  tl.run app, (require './vrender-main'), handlers, State
