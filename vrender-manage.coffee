tl = require 'talio'

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

module.exports = (state, channels) ->
  if (state.activeboards or []).length
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
              'Some update is not showing? '
              (form
                'ev-submit': tl.sendSubmit channels.initialFetch, {id: ab.id}
                className: "inline"
              ,
                (button {}, "trigger a sync")
              )
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
                    defaultValue: ab.subdomain
                    style: {"width":"148px","text-align":"right"}
                  )
                  ".websitesfortrello.com/ "
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
    )
  else
    (div className: "col-1-1",
      (h3 {}, "Here you'll be able to change your boards' subdomains or delete them, but you currently have no board set up.")
      (a
        className: 'button'
        href: '#/setup'
      , 'Turn a Board into a site now')
    )
