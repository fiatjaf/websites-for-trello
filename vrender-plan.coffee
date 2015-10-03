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
    (div {},
      (button
        'ev-click': tl.sendClick channels.togglePremium, true, {preventDefault: true}
      , 'Enable premium account')
    ) if not state.premium
    (div {},
      (h2 {}, 'The premium plan is enabled for you.')
      (button
        'ev-click': tl.sendClick channels.togglePremium , false, {preventDefault: true}
      , 'Disable premium account')

      (div className: 'container',
        (div className: 'col-1-2',
          (p {},
            'You owe:'
            (h1 {}, state.owe or '0.00')
          )
        )
        (div className: 'col-1-2',
          (button
            'ev-click': tl.sendClick channels.pay, '8.00', {preventDefault: true}
          , 'Pay $8')
        )
      )

      (h2 {}, 'Billing history')
      (table {},
        (thead {},
          (tr {},
            (th {}, 'Date')
            (th {}, 'Description')
            (th {}, 'Amount')
          )
        )
        (tbody {},
          (tr {},
            (td {}, row.date)
            (td {}, row.description)
            (td {}, if row.kind == 'payment' then '-' + row.amount else row.amount)
          ) for row in state.history
        )
      )
    ) if state.premium
  )
