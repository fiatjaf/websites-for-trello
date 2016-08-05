This repository contains the source code and build tools for the HTML + Javascript landing page and dashboard that appear on https://websitesfortrello.com/.

You probably don't want to use this, since it is a mix of simple not-great HTML and a CSS theme copied from MIT-licensed [Formspree](https://github.com/formspree/formspree) for the landing page; and a simple JS application (written in Coffeescript) built on top of [talio](https://www.npmjs.com/package/talio), a virtual-dom based, mercury-like framework with zero users. It also uses a bizarre build tool called [Sake](https://github.com/tonyfischetti/sake), which is in this case does nothing but run shell oneliners described in the [Sakefile](Sakefile).

The JS app shows at https://websitesfortrello.com/account/ does is to call methods on the [wft.api](https://bitbucket.org/websitesfortrello/wft.api), for (1) creating websites; (2) deleting websites; (3) setting subdomains for the website; (4) upgrading to the premium plan; and (5) deleting the website. The sign-in/sign-up process is also controlled by [wft.api](https://bitbucket.org/websitesfortrello/wft.api), that creates a Trello oAuth URL to which the user is redirected, and creates an account idempotently and logs the user in with cookies on the callback.

CORS is used in these API calls.
