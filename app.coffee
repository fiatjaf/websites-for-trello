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
  process.env.API_URL = 'http://' + process.env.DOMAIN.replace /0$/, 1
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
  process.env.API_URL = 'http://api.' + process.env.DOMAIN
  process.env.SITES_DOMAIN = process.env.DOMAIN

for node in document.querySelectorAll('[href^="#__"]')
  node.href = node.href.replace /.*__API_URL__/, process.env.API_URL

router = new Router()

State = tl.StateFactory
  user: null
  boards: []
  setupDone:
    board: null
    ready: false
  tab: 'create' # or ['manage', 'setupDone']

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
        ma('login', res.body.user) if State.get('user') != res.body.user
        State.change
          boards: res.body.boards
          activeboards: res.body.activeboards
          user: res.body.user
        if not silent
          router.redirect if res.body.activeboards.length then '#/' else '#/setup'
      else
        location.pathname = '/'
    ).catch(console.log.bind console)

  setupBoard: (State, data) ->
    self = @
    ma 'setup', data.name or data.id
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
            .get("http://#{board.subdomain}.#{process.env.SITES_DOMAIN}/")
            .end()
        ).then(->
          self.refresh State, true
          State.change 'setupDone.ready', true
          ma 'setupdone', board.id
        ).catch(op.retry.bind op)
    ).catch(console.log.bind console)

  deleteBoard: (State, data) ->
    self = @
    ma 'delete', data.id
    Promise.resolve().then(->
      superagent
        .del(process.env.API_URL + '/board/' + data.id)
        .withCredentials()
        .end()
    ).then(->
      self.refresh State
    ).catch(console.log.bind console)

  changeSubdomain: (State, data) ->
    self = @
    ma 'subdomain', data.subdomain
    Promise.resolve().then(->
      superagent
        .put(process.env.API_URL + '/board/' + data.id + '/subdomain')
        .send(value: data.subdomain)
        .withCredentials()
        .end()
    ).then(->
      self.refresh State
    ).catch(console.log.bind console)

  logout: (State) ->
    ma 'logout', State.get 'user'
    Promise.resolve().then(->
      superagent
        .get(process.env.API_URL + '/account/logout')
        .end()
    ).then(->
      location.pathname = '/'
    ).catch(console.log.bind console)

if '/account/' == location.pathname
  # setup router
  router
    .addRoute '#/setup', -> State.change 'tab', 'create'
    .addRoute '#/setup/again', -> State.change 'tab', 'create'
    .addRoute '#/logout', -> handlers.logout State
    .addRoute '#/', -> State.change 'tab', 'manage'
    .run('#/')

  # run this on startup
  handlers.refresh State
  # ~

  app = document.createElement 'div'
  document.querySelector('body > .row').insertBefore(app, document.querySelector('body > .row > .container'))
  tl.run app, (require './vrender-main'), handlers, State
