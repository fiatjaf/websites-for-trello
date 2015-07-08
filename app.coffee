Promise    = require 'lie'
superagent = (require 'superagent-promise')((require 'superagent'), Promise)
tl         = require 'talio'

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

if process.env.DEBUG
  API_URL = 'http://' + process.env.DOMAIN.replace /0$/, 1
else
  API_URL = 'http://api.' + process.env.DOMAIN

for node in document.querySelectorAll('[href^="#__"]')
  node.href = node.href.replace /.*__API_URL__/, API_URL

State = tl.StateFactory
  user: null
  boards: []
  tab: 'create' # or 'manage'

handlers =
  refresh: (State) ->
    Promise.resolve().then(->
      superagent
        .get(API_URL + '/account')
        .withCredentials()
        .type('json')
        .accept('json')
        .end()
    ).then((res) ->
      if res.body.user
        State.change
          boards: res.body.boards
          activeboards: res.body.activeboards
          user: res.body.user
          tab: if res.body.activeboards.length then 'manage' else 'create'
    ).catch(console.log.bind console)

  changeTab: (State, tabName) ->
    State.change 'tab', tabName

  setupBoard: (State, data) ->
    self = @
    Promise.resolve().then(->
      if data.name
        # create
        superagent
          .post(API_URL + '/board/setup')
          .send(name: data.name)
          .withCredentials()
          .end()
      else if data.id
        # reuse
        superagent
          .put(API_URL + '/board/setup')
          .send(id: data.id)
          .withCredentials()
          .end()
    ).then((res) ->
      self.refresh()
    ).catch(console.log.bind console)

  deleteBoard: (State, data) ->
    self = @
    Promise.resolve().then(->
      superagent
        .delete(API_URL + '/board/' + data.id)
        .withCredentials()
        .end()
    ).then(->
      self.refresh()
    ).catch(console.log.bind console)

  changeSubdomain: (State, data) ->
    self = @
    Promise.resolve().then(->
      superagent
        .put(API_URL + '/board/' + data.id + '/subdomain')
        .send(value: data.subdomain)
        .withCredentials()
        .end()
    ).then(->
      self.refresh()
    ).catch(console.log.bind console)

vrenderMain = (state, channels) ->
  vrenderTab = ({
    'create': vrenderCreate
    'manage': vrenderManage
  })[state.tab]

  (div className: "row section",
    (div
      className: "container"
      id: "header"
    ,
      (h1 {className: "center"}, state.user or '')
      (nav className: "center",
        (a
          href: "#"
          'ev-click': tl.sendClick channels.changeTab, 'manage', {preventDefault: true}
        , "Manage account")
        (a
          href: "#"
          'ev-click': tl.sendClick channels.changeTab, 'create', {preventDefault: true}
        , "Use another board")
        (a
          target: "_blank"
          href: "http://docs.websitesfortrello.com/"
        , "Documentation")
        (a {href: "#{API_URL}/account/logout"}, "Logout")
      )
    )
    (div className: "container narrow block",
      (vrenderTab state, channels)
    )
  )

vrenderCreate = (state, channels) ->
  (div className: "col-1-1",
    (form
      'ev-submit': tl.sendSubmit channels.setupBoard
    ,
      (h2 {}, "Create a new board")
      (input
        name: "name"
        placeholder: "#{state.user or 'someone'}'s site"
      )
      (button {type: "submit"}, "Create")
    )
    (form
      'ev-submit': tl.sendSubmit channels.setupBoard
    ,
      (h2 {}, "Use an existing board")
      (select name: "id",
        (option {value: b.id}, b.name) for b in state.boards
      )
      (button {type: "submit"}, "Use")
    )
  )

vrenderManage = (state, channels) ->
  (div className: "col-1-1",
    (h2 {}, "Active boards:")
    (ul {},
      (li {},
        (strong {}, ab.name)
        (ul {},
          (li {},
            (a
              target: "_blank"
              href: "https://trello.com/b/#{ab.id}"
            , "Go to the Trello board")
          )
          (li {},
            (a
              target: "_blank"
              href: "http://#{ab.subdomain}.websitesfortrello.com/"
            , "Visit site")
          )
          (li {},
            (form
              'ev-submit': tl.sendSubmit channels.changeSubdomain, {id: ab.id}
              className: "inline"
            ,
              (label {},
                "Change address to http://"
                (input
                  name: "subdomain"
                  defaultValue: ab.id
                  style: {"width":"148px","text-align":"right"}
                )
                ".websitesfortrello.com/"
              )
              (button {}, "change")
            )
          )
          (li {},
            (form
              'ev-submit': tl.sendSubmit channels.deleteBoard, {id: ab.id}
              className: "inline"
            ,
              (button {}, "disable site")
            )
          )
        )
      ) for ab in state.activeboards
    )
  ) if (state.activeboards or []).length

# run this on startup
handlers.refresh State
# ~

if '/account/' == location.pathname
  app = document.createElement 'div'
  document.querySelector('body > .row').insertBefore(app, document.querySelector('body > .row > .container'))
  tl.run app, vrenderMain, handlers, State
