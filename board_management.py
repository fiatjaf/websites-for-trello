from trello import TrelloApi # type: ignore
import requests
import sys
import os

pwd = os.path.dirname(os.path.realpath(__file__))

def remove_bot(id):
    r = requests.delete('https://api.trello.com/1/boards/' + id + '/members/' + os.environ['TRELLO_BOT_ID'], params={
        'key': os.environ['TRELLO_BOT_API_KEY'],
        'token': os.environ['TRELLO_BOT_TOKEN']
    })
    if not r.ok:
        print(r.text)
        raise Exception('could not remove bot from board.')

def add_bot(user_token, id):
    # > add bot
    r = requests.put('https://api.trello.com/1/boards/' + id + '/members/' + os.environ['TRELLO_BOT_ID'], params={
        'key': os.environ['TRELLO_API_KEY'],
        'token': user_token
    }, data={
        'type': 'normal'
    })
    if not r.ok:
        print(r.text)
        raise Exception('could not add bot to board.')

def board_setup(id, username=None):
    print(':: MODEL-UPDATES :: board_setup for ', id)

    # > from now on all actions performed by the bot
    trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])

    # > change description
    trello.boards.update_desc(id, 'This is your board description. You can change it on Trello!')

    # > add default lists
    default_lists = {
        '#pages': None,
        '_preferences': None,
    }

    lists = trello.boards.get_list(id, fields='name,closed', filter='all')
    for l in lists:
        if l['name'] in ('_preferences', '#pages'):
            # only manipulate one, if there are many with the same name
            if default_lists[l['name']] == None:
                # bring back if archived
                if l['closed']:
                    trello.lists.update_closed(l['id'], 'false')
                default_lists[l['name']] = l['id']
            else:
                if l['name'] == '_preferences':
                    # rename to something that will not interfere
                    trello.lists.update_name(l['id'], '_preferences (old)')
                    trello.lists.update_closed(l['id'], 'true') # and archive.

    for name, list_id in default_lists.items():
        # create now (only if it doesn't exist)
        if not list_id:
            default_lists[name] = trello.boards.new_list(id, name)['id']

    # get user info
    if username:
        user = trello.members.get(username, fields='username,gravatarHash,avatarHash,bio')
        image = '//trello-avatars.s3.amazonaws.com/%s/170.png' % user['avatarHash'] if user.get('avatarHash') else '//gravatar.com/avatar/%s' % user['gravatarHash'] if user.get('gravatarHash') else None
        imagemd = '![%s](%s)' % (username, image) if image else ''
        aside_text = '%s\n\n# %s\n\n%s' % (imagemd, username, user.get('bio', 'Hello and welcome to this website.'))
    else:
        aside_text = 'Hello and welcome to this website.'

    # > add cards to lists
    special_cards = {
        'includes': None,
        'nav': None,
        'posts-per-page': None,
        'domain': None,
        'favicon': None,
        'excerpts': None,
        'aside': None,
        'header': None,
    }
    defaults = {
        'includes': 'See instructions for using this special card at http://docs.websitesfortrello.com/the-basics/customization-through-javascript-and-css/\n\nIf you are in a hurry and want to quickly add CSS or JS code to your site, try using the [Trello Attachment Editor](https://websitesfortrello.github.io/attachments/)',
        'nav': 'See instructions for customizing navigation at http://docs.websitesfortrello.com/the-basics/navigation/',
        'posts-per-page': '7',
        'excerpts': '0',
        'aside': aside_text,
        'header': '',
        'domain': '',
        'favicon': 'http://lorempixel.com/32/32/'
    }
    includes_checklists = {
        'themes': {
            '[CSS for the __Lebo__ theme](//websitesfortrello.github.io/classless/themes/lebo.css)': 'false',
            '[CSS for the __Jeen__ theme](//websitesfortrello.github.io/classless/themes/jeen.css)': 'false',
            '[CSS for the __Wardrobe__ theme](//websitesfortrello.github.io/classless/themes/wardrobe.css)': 'false',
            '[CSS for the __Ghostwriter__ theme](//websitesfortrello.github.io/classless/themes/ghostwriter.css)': 'false',
            '[CSS for the __Barbieri__ theme](//websitesfortrello.github.io/classless/themes/barbieri.css)': 'true',
            '[CSS for the __Tacit__ theme](//websitesfortrello.github.io/classless/themes/tacit.css)': 'false',
            '[CSS for the __Festively__ theme](//websitesfortrello.github.io/classless/themes/festively.css)': 'false',
            '[CSS for the __Aluod__ theme](//websitesfortrello.github.io/classless/themes/aluod.css)': 'false',
            '[CSS for the __dbyll__ theme](//websitesfortrello.github.io/classless/themes/dbyll.css)': 'false',
        },
        'themes-js': {
            '[Javascript for the __Ghostwriter__ theme](//websitesfortrello.github.io/classless/themes/ghostwriter.js)': 'false',
            '[Javascript for the __Festively__ theme](//websitesfortrello.github.io/classless/themes/festively.js)': 'false',
            '[Javascript for the __Aluod__ theme](//websitesfortrello.github.io/classless/themes/aluod.js)': 'false',
        },
        'utils': {
            '[Add __Eager__ -- a service that includes apps for you, take a look at https://eager.io/ (replace with your own code)](//fast.eager.io/<your-code-from-eager.io>.js)': 'false',
            '[Simple forms styling](//websitesfortrello.github.io/includes/forms.css)': 'true',
            '[Label colors, Trello defaults](//websitesfortrello.github.io/includes/label-colors-trello.css)': 'true',
            '[Hide author information](//websitesfortrello.github.io/includes/hide-author.css)': 'false',
            '[Customize each page individually by including CSS and JS attachments on each card](//websitesfortrello.github.io/includes/per-card-includes.js)': 'false',

            '[Add __Google Analytics__ -- add your code by editing this item (click here) -->](https://temperos.alhur.es/http://websitesfortrello.github.io/includes/add-google-analytics.js?code=YOUR_GOOGLE_ANALYTICS_TRACKING_CODE)': 'false',
            '[Add __Disqus__ -- set your shortname by clicking at the side of this item -->](https://temperos.alhur.es/http://websitesfortrello.github.io/includes/add-disqus.js?shortname=YOUR_DISQUS_SHORTNAME)': 'false',
            '[Show image attachments as actual images instead of links](//websitesfortrello.github.io/includes/show-attachments-as-images.js)': 'false',
            '[Change footer text -- edit the text by clicking here at the side -->](https://temperos.alhur.es/http://websitesfortrello.github.io/includes/replace-footer-text.css?text=YOUR_FOOTER_TEXT)': 'false',
            '[Change title text -- edit the text by clicking here at the side -->](https://temperos.alhur.es/http://websitesfortrello.github.io/includes/replace-title-text.css?text=YOUR_TITLE_TEXT)': 'false',
            '[Hide posts date](//websitesfortrello.github.io/includes/hide-date.css)': 'false',
            '[Hide category title on article pages](//websitesfortrello.github.io/includes/hide-category-header-on-article-pages.css)': 'true',
            '[Turn Youtube links into embedded videos](//websitesfortrello.github.io/includes/youtube-embed.js)': 'true',
            '[Add __Hypothes.is__ annotations](//hypothes.is/embed.js)': 'true',
            '[Use a font from Google Fonts in your article bodies -- choose font by editing this checkbox -->](https://temperos.alhur.es/http://websitesfortrello.github.io/includes/text-font-from-google-fonts.js?FONT-NAME=replace+the+font+name+here+with+plus+signs+just+like+google+fonts+presents+them+to+you+when+you+choose+them)': 'false',
            '[Open external links in new tabs](//websitesfortrello.github.io/includes/open-links-in-new-page.js)': 'false',
            '[Expand (or shrink) images to the full-width of the article](//websitesfortrello.github.io/includes/expand-images-to-a-hundred-percent.css)': 'false',
            '[Center images in articles](//websitesfortrello.github.io/includes/center-images.css)': 'true',
            '[Hide attachment links from the bottom of articles](//websitesfortrello.github.io/includes/hide-attachment-links-in-the-bottom.css)': 'true',
        }
    }

    # cards already existing
    cards = trello.lists.get_card(default_lists['_preferences'], fields='name,closed', filter='all')
    for c in cards:
        if c['name'] in special_cards:
            # revive archived cards
            if c['closed']:
                trello.cards.update_closed(c['id'], 'false')
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
            checklists = trello.cards.get_checklist(card_id, fields='name')
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
            checklists = trello.cards.get_checklist(card_id, fields='name')
            for checkl in checklists:
                trello.cards.delete_checklist_idChecklist(checkl['id'], card_id)

            # include our default checklist
            checkl = trello.cards.new_checklist(card_id, None)
            trello.checklists.new_checkItem(checkl['id'], '__lists__')
            trello.checklists.new_checkItem(checkl['id'], '[About](/about)')

    cards = trello.lists.get_card(default_lists['#pages'], fields='name', filter='all')
    for c in cards:
        if c['name'] in ('/about', '/about/'):
            # already exist, so ignore, leave it there
            break
    else:
        # didn't find /about, so create it
        trello.cards.new('/about', default_lists['#pages'], desc='''# About me

Lorem ipsum dolor sit amet, malorum quaestio ius ne, ad vulputate assueverit per. Est ea porro propriae sententiae, sed ea graecis offendit temporibus. Nusquam menandri indoctum eum at, mentitum signiferumque ea pri, cu duo fabellas deseruisse. Ne choro tantas habemus ius, ei cum illum volumus. No nominati laboramus per. Nec no dolore partiendo democritum.''')

    # > create webhook
    r = requests.put('https://api.trello.com/1/webhooks', params={
        'key': os.environ['TRELLO_BOT_API_KEY'],
        'token': os.environ['TRELLO_BOT_TOKEN']
    }, data={
        'callbackURL': os.environ['WEBHOOK_URL'] + '/board',
        'idModel': id
    }) 
    if not r.ok:
        print(r.text)
        raise Exception('could not add webhook')

    print(':: MODEL-UPDATES :: board_setup finished for', id)

if __name__ == '__main__':
    import app
    if len(sys.argv) == 2:
        board_setup(sys.argv[1])
