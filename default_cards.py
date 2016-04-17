from trello import TrelloApi # type: ignore
import requests

lists = {
    '#pages': None,
    'articles': None,
    '_ drafts': None
}

cards = {
    '#pages': {
        '/about': '# About me

    Lorem ipsum dolor sit amet, malorum quaestio ius ne, ad vulputate assueverit per. Est ea porro propriae sententiae, sed ea graecis offendit temporibus. Nusquam menandri indoctum eum at, mentitum signiferumque ea pri, cu duo fabellas deseruisse. Ne choro tantas habemus ius, ei cum illum volumus. No nominati laboramus per. Nec no dolore partiendo democritum.''',
    },
    'articles': {
        'Fish, the animal': {
            'desc': 'A **fish** is any member of a [paraphyletic](https://en.wikipedia.org/wiki/Paraphyletic) group of organisms that consist of all [gill](https://en.wikipedia.org/wiki/Gill)-bearing [aquatic](https://en.wikipedia.org/wiki/Aquatic_animal) [craniate](https://en.wikipedia.org/wiki/Craniate) animals that lack [limbs](https://en.wikipedia.org/wiki/Limb_(anatomy)) with digits. Included in this definition are the living [hagfish](https://en.wikipedia.org/wiki/Hagfish), [lampreys](https://en.wikipedia.org/wiki/Lamprey), and [cartilaginous](https://en.wikipedia.org/wiki/Chondrichthyes) and [bony](https://en.wikipedia.org/wiki/Bony_fish) fish, as well as various extinct related groups. Most fish are ectothermic ("cold-blooded"), allowing their body temperatures to vary as ambient temperatures change, though some of the large active swimmers like [white shark](https://en.wikipedia.org/wiki/White_shark) and [tuna](https://en.wikipedia.org/wiki/Tuna) can hold a higher [core temperature](https://en.wikipedia.org/wiki/Core_temperature). Fish are abundant in most bodies of water. They can be found in nearly all aquatic environments, from high mountain streams (e.g., char and gudgeon) to the abyssal and even hadal depths of the deepest oceans (e.g., gulpers and anglerfish). With 33,100 described species, fish exhibit greater species diversity than any other group of vertebrates.

[Fish](http://fishshell.com/) is also a shell for OS X, Linux and the rest of the family.

---

_Sample content from [Wikipedia](https://upload.wikimedia.org/wikipedia/commons/2/23/Georgia_Aquarium_-_Giant_Grouper_edit.jpg)_.'
            'attachments': ['https://upload.wikimedia.org/wikipedia/commons/2/23/Georgia_Aquarium_-_Giant_Grouper_edit.jpg']
        },
    },
    '_ drafts': {

    },
}

def create_default_cards(board_id):
    get_or_create_default_lists(board_id)

def get_or_create_default_lists(board_id):
    
cards = trello.lists.get_card(default_lists['#pages'], fields='name', filter='all')
for c in cards:
    if c['name'] in ('/about', '/about/'):
        # already exist, so ignore, leave it there
        break
else:
    # didn't find /about, so create it
    trello.cards.new('/about', default_lists['#pages'], desc='''# About me

