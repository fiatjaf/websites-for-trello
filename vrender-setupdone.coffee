tl = require 'talio'

{div, main, span, pre, nav, section,
 small, i, p, b, a, button, code,
 h1, h2, h3, h4, strong,
 form, legend, label, input, textarea, select, label, option,
 table, thead, tbody, tfoot, tr, th, td,
 dl, dt, dd,
 ul, li} = require 'virtual-elements'

module.exports = (setupDoneState, channels) ->
  board = setupDoneState.board

  (div className: "container narrow block",
    (div
      className: "col-1-1"
      style: {"text-align":"center"}
    ,
      (div innerHTML: svgbox)
      (div {},
        (p {}, "Fetching your data from Trello...")
        (small {}, "(this usually takes a minute, but if your Board has a lot of content on it 3 minutes is not too much time -- you can close this window and come back later if you want to)")
      )
    ) if not setupDoneState.ready
    (div
      className: "col-1-1"
      id: "ready"
    ,
      (p {},
        "Your Trello-powered website is live at "
        (a
          target: "_blank"
          href: "http://#{board.subdomain}.#{process.env.SITES_DOMAIN}"
        ,
          "#{board.subdomain}.#{process.env.SITES_DOMAIN}")
        ". We're still applying some default configurations and adding some styles to it, but this will take less than a minute."
      )
      (p {},
        "You can view it right now, and you can go to your "
        (a
          target: "_blank"
          href: "https://trello.com/b/#{board.shortLink}"
        , "Trello board")
        " to edit its contents and preferences. To change the subdomain where your website is hosted (under "
        (span {className: "code"}, ".#{process.env.SITES_DOMAIN}")
        ") visit your "
        (a
          href: "#/"
        , "main account page")
        "."
      )
      (p {},
        "If you want to use another board, you can just go through "
        (a
          href: "#/setup/again"
        , "our setup process again")
        "."
      )
      (p {},
        "To use your own domain in your site, just "
        (a
          href: "#/plan"
        , "upgrade your account")
        " for only "
        (span {className: "code"}, "$17.00 / month")
        "."
      )
    ) if setupDoneState.ready
  )

svgbox = '''
<style type="text/css">
uiload {
  display: inline-block;
  position: relative; }
  uiload > div {
    position: relative; }
@-webkit-keyframes uil-triangle-rotate {
  0% {
    -ms-transform: rotate(0deg);
    -moz-transform: rotate(0deg);
    -webkit-transform: rotate(0deg);
    -o-transform: rotate(0deg);
    transform: rotate(0deg); }

  100% {
    -ms-transform: rotate(120deg);
    -moz-transform: rotate(120deg);
    -webkit-transform: rotate(120deg);
    -o-transform: rotate(120deg);
    transform: rotate(120deg); } }

@-moz-keyframes uil-triangle-rotate {
  0% {
    -ms-transform: rotate(0deg);
    -moz-transform: rotate(0deg);
    -webkit-transform: rotate(0deg);
    -o-transform: rotate(0deg);
    transform: rotate(0deg); }

  100% {
    -ms-transform: rotate(120deg);
    -moz-transform: rotate(120deg);
    -webkit-transform: rotate(120deg);
    -o-transform: rotate(120deg);
    transform: rotate(120deg); } }

@-ms-keyframes uil-triangle-rotate {
  0% {
    -ms-transform: rotate(0deg);
    -moz-transform: rotate(0deg);
    -webkit-transform: rotate(0deg);
    -o-transform: rotate(0deg);
    transform: rotate(0deg); }

  100% {
    -ms-transform: rotate(120deg);
    -moz-transform: rotate(120deg);
    -webkit-transform: rotate(120deg);
    -o-transform: rotate(120deg);
    transform: rotate(120deg); } }

@keyframes uil-triangle-rotate {
  0% {
    -ms-transform: rotate(0deg);
    -moz-transform: rotate(0deg);
    -webkit-transform: rotate(0deg);
    -o-transform: rotate(0deg);
    transform: rotate(0deg); }

  100% {
    -ms-transform: rotate(120deg);
    -moz-transform: rotate(120deg);
    -webkit-transform: rotate(120deg);
    -o-transform: rotate(120deg);
    transform: rotate(120deg); } }

.uil-triangle-css {
  background: none;
  position: relative;
  width: 200px;
  height: 200px; }

.uil-triangle-css > div > div {
  position: absolute;
  width: 0;
  height: 0;
  border-top: 56px solid black;
  border-left: 33px solid transparent;
  border-right: 33px solid transparent; }

.uil-triangle-css > div {
  position: absolute;
  width: 66px;
  height: 36px;
  -ms-animation: uil-triangle-rotate 1.4s linear infinite;
  -moz-animation: uil-triangle-rotate 1.4s linear infinite;
  -webkit-animation: uil-triangle-rotate 1.4s linear infinite;
  -o-animation: uil-triangle-rotate 1.4s linear infinite;
  animation: uil-triangle-rotate 1.4s linear infinite; }

.uil-triangle-css > div:nth-of-type(1) {
  top: 40px;
  left: 30px; }
  .uil-triangle-css > div:nth-of-type(1) > div {
    border-top: 56px solid #0079BF; }

.uil-triangle-css > div:nth-of-type(2) {
  top: 40px;
  left: 100px; }
  .uil-triangle-css > div:nth-of-type(2) > div {
    border-top: 56px solid #F2D600; }

.uil-triangle-css > div:nth-of-type(3) {
  top: 110px;
  left: 67px; }
  .uil-triangle-css > div:nth-of-type(3) > div {
    border-top: 56px solid #0079BF; }
</style>
<!--?xml version="1.0" encoding="utf-8"?-->
<svg width="164px" height="164px" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid" class="uil-triangle">
  <rect x="0" y="0" width="100" height="100" fill="none" class="bk"></rect>
  <path d="M34.5,52.4c-0.8,1.4-2.2,1.4-3,0L17.2,27.6C16.4,26.2,17,25,18.7,25h28.6c1.6,0,2.3,1.2,1.5,2.6L34.5,52.4z" fill="#0079BF" transform="rotate(80.1544 33 35)">
    <animateTransform attributeName="transform" type="rotate" from="0 33 35" to="120 33 35" repeatCount="indefinite" dur="1.4s"></animateTransform>
  </path>
  <path d="M68.5,52.4c-0.8,1.4-2.2,1.4-3,0L51.2,27.6C50.4,26.2,51,25,52.7,25h28.6c1.7,0,2.3,1.2,1.5,2.6L68.5,52.4z" fill="#F2D600" transform="rotate(80.1544 67 35)">
    <animateTransform attributeName="transform" type="rotate" from="0 67 35" to="120 67 35" repeatCount="indefinite" dur="1.4s"></animateTransform>
  </path>
  <path d="M51.5,82.4c-0.8,1.4-2.2,1.4-3,0L34.2,57.6C33.4,56.2,34,55,35.7,55h28.6c1.7,0,2.3,1.2,1.5,2.6L51.5,82.4z" fill="#0079BF" transform="rotate(80.1544 50 65)">
    <animateTransform attributeName="transform" type="rotate" from="0 50 65" to="120 50 65" repeatCount="indefinite" dur="1.4s"></animateTransform>
  </path>
</svg>
'''
