from trello import TrelloApi
import requests
import os

pwd = os.path.dirname(os.path.realpath(__file__))

def board_clear(id):
    pass

def board_setup(user_token, id):
    # > remove bot (hoping this will delete the webhook)
    r = requests.delete('https://api.trello.com/1/boards/' + id + '/members/' + os.environ['TRELLO_BOT_ID'], params={
        'key': os.environ['TRELLO_API_KEY'],
        'token': user_token
    })
    # > add bot
    r = requests.put('https://api.trello.com/1/boards/' + id + '/members/' + os.environ['TRELLO_BOT_ID'], params={
        'key': os.environ['TRELLO_API_KEY'],
        'token': user_token
    }, data={
        'type': 'normal'
    })
    if not r.ok:
        print r.text
        raise Exception('could not add bot to board.')

    # > from now on all actions performed by the bot
    trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])

    # > change description
    trello.boards.update_desc(id, 'This is a website and also a Trello board, and vice-versa!')

    # > add default lists
    default_lists = {
        '#pages': None,
        '_preferences': None,
    }

    lists = trello.boards.get_list(id, fields=['name', 'closed'])
    for l in lists:
        if l['name'] in ('_preferences', '#pages'):
            # bring back if archived
            if l['closed']:
                trello.lists.update_closed(l['id'], False)
            default_lists[l['name']] = l['id']

    for name, list_id in default_lists.items():
        # create now (only if it doesn't exist)
        if not list_id:
            list_id = trello.boards.new_list(id, name)['id']

    # > add cards to lists
    special_cards = {
        'instructions': None,
        'includes': None,
        'nav': None,
        'posts-per-page': None,
        'domain': None,
        'favicon': None
    }
    defaults = {
        'instructions': open(pwd + '/cards/instructions.md').read(),
        'includes': open(pwd + '/cards/includes.md').read(),
        'nav': open(pwd + '/cards/nav.md').read(),
        'posts-per-page': '7',
        'domain': '',
        'favicon': 'http://lorempixel.com/32/32/'
    }
    includes_checklists = {
        'themes': {
            '[CSS for the __Lebo__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/lebo.css)': 'true',
            '[CSS for the __Jeen__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/jeen.css)': 'false',
            '[CSS for the __Wardrobe__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/wardrobe.css)': 'false',
            '[CSS for the __Ghostwriter__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/ghostwriter.css)': 'false',
            '[CSS for the __Festively__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/festively.css)': 'false',
            '[CSS for the __Aluod__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/aluod.css)': 'false',
            '[CSS for the __dbyll__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/dbyll.css)': 'false',
        },
        'themes-js': {
            '[Javascript for the __Ghostwriter__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/ghostwriter.js)': 'false',
            '[Javascript for the __Festively__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/festively.js)': 'false',
            '[Javascript for the __Aluod__ theme](//rawgit.com/fiatjaf/classless/gh-pages/themes/aluod.js)': 'false',
        },
        'utils': {
            '[Hide author information](https://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/5517c2096e37332144e497538c169ff503e1314c/hide-author.css)': 'false',

            '[Google Analytics -- edit here to add your code](http://temperos.alhur.es/http://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/e4060e9348079792a098d42fa8ad8b3c2bf2aee5/add-google-analytics.js?code=YOUR_GOOGLE_ANALYTICS_TRACKING_CODE)': 'false',
            '[Disqus -- edit here to add your shortname](http://temperos.alhur.es/http://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/29721482d7cf63d6bb077cf29a324d799017d068/add-disqus.js?shortname=YOUR_DISQUS_SHORTNAME)': 'false',
            '[Show image attachments as actual images instead of links](http://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/567162cc78cff0fab4bb9de1785743b9a87234ca/show-attachments-as-images.js)': 'false',
            '[Change footer text -- edit here to choose the text](http://temperos.alhur.es/http://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/a77b24106a2fe33bd804b9f939e33b040aeae8bb/replace-footer-text.css?text=YOUR_FOOTER_TEXT)': 'false',
            '[Hide posts date](https://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/8dcf95329c21791dd327df47bb1e2a043453548f/hide-date.css)': 'false',
            '[Hide category title on article pages](https://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/dcb70e2adc030f21f58c644757877a07e01479b5/hide-category-header-on-article-pages.css)': 'true',
            '[Show post excerpts on home page and category pages -- edit the number of characters and "read more" text](http://temperos.alhur.es/https://rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/6ccdca1b221b70f6abd87ef3875e469ec08c9a5e/show-excerpts.js?limit=200&read_more_text=(read+more...))': 'false',
            '[Turn Youtube links into embedded videos](https://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/2a892b56fe14e0b75452394148b2b29015a76ef7/youtube-embed.js)': 'true',
            '[Add Carnival comments -- edit your site id](http://temperos.alhur.es/https://cdn.rawgit.com/fiatjaf/24aee0052afc73035ee6/raw/6d6b95595339369d84d51d127be45af7f5926d7e/add-carnival-comments.js?YOUR-SITE-ID=)': 'false',
        }
    }

    # cards already existing
    cards = trello.lists.get_card(default_lists['_preferences'], fields=['name', 'closed'])
    for c in cards:
        if c['name'] in special_cards:
            # revive archived cards
            if c['closed']:
                trello.cards.update_closed(c['id'], False)
            special_cards[c['name']] = c['id']

    # create cards or reset values
    for name, card_id in special_cards.items():
        value = defaults[name]

        if card_id:
            trello.cards.update_desc(card_id, value)
        else:
            c = trello.cards.new(name, default_lists['_preferences'], desc=value)
            card_id = c['id']

        # include basic themes as a checklist
        if name == 'includes':

            # delete our default checklists
            checklists = trello.cards.get_checklist(card_id, fields=['name'])
            for checkl in checklists:
                if checkl['name'] in includes_checklists:
                    trello.cards.delete_checklist_idChecklist(checkl['id'], card_id)
            # add prefilled checklists:
            for checklist_name, checklist in includes_checklists.items():
                # the API wrapper doesn't have the ability to add named checklists
                checkl = requests.post("https://trello.com/1/cards/%s/checklists" % card_id,
                    params={'key': os.environ['TRELLO_BOT_API_KEY'],
                            'token': os.environ['TRELLO_BOT_TOKEN']},
                    data={'name': checklist_name}
                ).json()

                for checkitem, state in checklist.items():
                    # the API wrapper doesn't have the ability to add checked items
                    requests.post("https://trello.com/1/checklists/%s/checkItems" % checkl['id'],
                        params={'key': os.environ['TRELLO_BOT_API_KEY'],
                                'token': os.environ['TRELLO_BOT_TOKEN']},
                        data={'name': checkitem,
                              'checked': state}
                    )
        elif name == 'nav':
            # delete our default checklists
            checklists = trello.cards.get_checklist(card_id, fields=['name'])
            for checkl in checklists:
                trello.cards.delete_checklist_idChecklist(checkl['id'], card_id)

            # include our default checklist
            checkl = trello.cards.new_checklist(card_id, None)
            trello.checklists.new_checkItem(checkl['id'], '__lists__')
            trello.checklists.new_checkItem(checkl['id'], '[About](/about)')

    cards = trello.lists.get_card(default_lists['#pages'], fields=['name'])
    for c in cards:
        if c['name'] in ('/about', '/about/'):
            # already exist, so ignore, leave it there
            break
    else:
        # didn't find /about, so create it
        trello.cards.new('/about', default_lists['#pages'], desc=open(pwd + '/cards/about.md').read())

    # > create webhook
    r = requests.put('https://api.trello.com/1/webhooks', params={
        'key': os.environ['TRELLO_BOT_API_KEY'],
        'token': os.environ['TRELLO_BOT_TOKEN']
    }, data={
        'callbackURL': os.environ['WEBHOOK_URL'] + '/board',
        'idModel': id
    }) 
    if not r.ok:
        print r.text
        raise Exception('could not add webhook')
