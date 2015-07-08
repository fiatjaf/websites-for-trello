Basically:

  * Every list represent a "section" of your site, and every section can have various cards, which are listed like blog posts.
  * The date displayed for cards is their creation date. You can override these dates and show custom dates for cards (for example, if you want to fake the creation date of some post) with **Due date**.
  * Card descriptions are the content of the card, markdown is rendered to HTML just like Trello does inside its interface.
  * Checklists you add to cards are shown just like checklists in the rendered page. This can be useful, or don't, you decide.
  * Attachments are also added to cards as a list of attachments in the end of the posts, images added as `<img>` tags and so rendered, but you can also link to them inside your cards with markdown to show inline images.
  * Cards with names starting with a `_` are hidden, so you can have drafts. This also works for lists and all the cards under them.
  * The `_preferences` list is special and has some special cards with special properties, mostly for configuration.
  * Also special is the board description, which is translated as your site's description. To edit the board's description, find and click a small icon resembling various lines next to the board name.
  * Most customizations (hiding this and that information from your site, reorganizing objects in the rendered pages, ajaxifying navigation and so on) can and should be done with CSS and Javascript, since modifying the HTML basic template is not possible. Go to your **includes** card in this same list and include/link everything from there.

### About the `_preferences` list:

Currently the following configurations are supported (all them set by modifying their respective card in the `_preferences` list)

  * __includes__: as said before, this is used for adding CSS and Javascript to your site
  * __favicon__: a URL to an image (it can be hosted inside your board) that will be served as your site's browser icon (you know, that icon shown on the browser tabs and favorites for each website)
  * __posts-per-page__: number of posts shown in each list page and the homepage, the default is 7
  * __nav__: this card controls the links you'll have in your main site menu
  * __domain__: when you get [support for a custom domain](http://websitesfortrello.com/account) you go to this card and write your domain there in the description

### About the `#pages` list:

You can add as many cards as you want to the `#pages` list. The card titles must be the relative address where they are going to be found, i.e., if you want a page to be found at `http://yoursite.com/about/contact`, name it `/about/contact`. As with all other cards, its contents, attachments and checklists will be rendered as the contents of the actual page.

---

## Documentation

For more comprehensive documentation, see http://docs.websitesfortrello.com/.
