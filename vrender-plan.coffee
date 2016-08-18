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
        '.'
      )
      (p {},
        (b {}, '$17 / month')
        ', unlimited websites, unlimited custom domains.'
      )
      (button
        'ev-click': tl.sendClick channels.togglePremium, true, {preventDefault: true}
        className: 'block button'
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
    ) if state.premium
  )
