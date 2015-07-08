In this card you should keep a checklist with the items you want to be shown on the main navigation menu of your site. If you delete this card or all the items from the checklist there will be no menu.

Each checklist item can take the form of a canonical markdown link, i.e., `[Text of the link](http://actual-address/)`, this will ensure that they show the text you want them to show and point to the correct address you want them to point.

To point to pages inside your own site, you can use relative links, i.e., instead of writing `http://somewhere.com/path/to/page` you write just `/path/to/page`.

There is a special item (which is the one enabled by default) that displays automatically links to all your Trello lists individual pages (these pages list the cards inside them in the order they are in the Trello list itself). The special item is identified by the following value: `__lists__`. You can remove the special item and still point to specific lists by manually writing their relative addresses in the checklist, and you can use the special item along with other items, before or after it.

It doesn't matter if the items are checked or not.
