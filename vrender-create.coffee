tl = require 'talio'

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

module.exports = (state, channels) ->
  (div className: "col-1-1",
    (form
      'ev-submit': tl.sendSubmit channels.setupBoard
    ,
      (h2 {}, "Create a new board")
      (input
        name: "name"
        placeholder: "#{state.user or 'someone'}'s site"
      )
      ' '
      (button {type: "submit"}, "Create")
    )
    (form
      'ev-submit': tl.sendSubmit channels.setupBoard
    ,
      (h2 {}, "Use an existing board")
      (select name: "id",
        (option {value: b.id}, b.name) for b in state.boards
      )
      ' '
      (button {type: "submit"}, "Use")
    )
  )
