tl    = require 'talio'
Money = require 'math-money'

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

module.exports = (state, channels) ->
  money = (ints) ->
    pfed = Money.factory('$', { decimals: 2, prefix: '_' }).raw(ints).format()
    return pfed.slice(2)

  (div className: "col-1-1",
    (div {},
      (h2 {className: 'center'}, 'You are using a free account.')
      (p {},
        'Upgrade to gain access to '
        (b {}, 'custom domains')
        ' and up to '
        (b {}, '25,000 page views')
        '.'
      )
      (p {},
        'You can enable the premium features without paying anything, test them as you wish and decide if you want to pay later. If you have any question, please use our contact form or email us on '
        (b {}, 'websitesfortrello@boardthreads.com')
        '.'
      )
      (button
        'ev-click': tl.sendClick channels.togglePremium, true, {preventDefault: true}
        className: 'block'
      ,
        'Enable premium account'
      )
    ) if not state.premium
    (div {},
      (h2 {className: 'center'}, 'You are using a premium account.')
      (button
        className: 'block'
        'ev-click': tl.sendClick channels.togglePremium , false, {preventDefault: true}
      , 'Disable premium account')

      (div className: 'container',
        (div className: 'col-1-2',
          (p {},
            'You owe:'
            (h1 {}, '$' + (if state.owe then money(state.owe) else '0.00'))
          )
        )
        (div className: 'col-1-2',
          (button
            className: 'block'
            'ev-click': tl.sendClick channels.pay, money(state.owe), {preventDefault: true}
          , 'Pay with PayPal') if money(state.owe) != '0.00'
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
            (td {style: {'text-align': 'right'}},
              if not row.cents then '' else if row.kind == 'payment' then '$ ' + money(-row.cents) else '$ ' + money(row.cents)
            )
          ) for row in state.history
        )
      ) if state.history.length > 0
    ) if state.premium
  )
