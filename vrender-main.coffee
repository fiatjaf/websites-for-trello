tl = require 'talio'

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

module.exports = (state, channels) ->
  vrenderTab = ({
    'create': require './vrender-create'
    'manage': require './vrender-manage'
    'setupDone': require './vrender-setupdone'
  })[state.tab]

  (div className: "row section",
    (div
      className: "container"
      id: "header"
    ,
      (h1 {className: "center"}, state.user or '')
      (nav className: "center",
        (a
          href: "#/"
        , "Manage account")
        (a
          href: "#/setup"
        , "Use another board")
        (a
          target: "_blank"
          href: "http://docs.websitesfortrello.com/"
        , "Documentation")
        (a
          href: "#/logout"
        , "Logout")
      )
    )
    (div className: "container narrow block",
      (vrenderTab (state[state.tab] or state), channels)
    )
  )

