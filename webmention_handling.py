from trello import TrelloApi
from models import User, Board, List, Card, Label, Comment
from urlparse import urlparse
from sqlalchemy import func, select, table, text, column
from app import db
import os
import went
import requests

def handle_webmention(source, target):
    # find target card
    parsedtarget = urlparse(target)
    pathsplit = filter(bool, parsedtarget.path.split('/'))
    if parsedtarget.netloc.endswith(os.environ['DOMAIN']):
        ok = Board.query.filter_by(subdomain=parsedtarget.netloc.split('.')[0]).first()
    else:
        ok = len(db.engine.execute(select([func.preferences(parsedtarget.netloc)])).first()[0].keys()) > 2
    if not ok or len(pathsplit) != 2:
        print ':: MODEL-UPDATES :: webmention targetting wrong place:', target
        return

    list = List.query.filter_by(slug=pathsplit[0]).first()
    if list:
        card = list.cards.filter_by(slug=pathsplit[1]).first()
    elif pathsplit[0] == 'c':
        card = Card.query.get(pathsplit[1])
    if not card:
        print ':: MODEL-UPDATES :: no card found for webmention:', target
        return

    # parse the webmention and get its contents
    try:
        print 'source=%s, target=%s' % (source, target)
        webmention = went.Webmention(url=source, target=target, alternative_targets=[
            'http://%s/c/%s' % (parsedtarget.netloc, card.id),
            'http://%s/c/%s' % (parsedtarget.netloc, card.shortLink),
        ])
    except (went.NoURLInSource, went.NoContent):
        webmention = None
    if not webmention or not hasattr(webmention, 'body'):
        print ':: MODEL-UPDATES :: no webmention body or other problem at', source
        return

    raw = ":paperclip: **[{author_name}]({author_url})**\n\n{body}\n\non [{date}]({source_url}) via _[{source_display}]({source_url})_".format(
        author_name=webmention.author.name.encode('utf-8'),
        author_url=webmention.author.url,
        body='\n'.join(map(lambda l: '> ' + l, webmention.body.encode('utf-8').split('\n'))),
        date=webmention.date,
        source_url=webmention.url,
        source_display=getattr(webmention, 'via') or urlparse(source).netloc
    )

    # check if it already exists
    comment = Comment.query.filter_by(card_id=card.id, source_url=webmention.url).first()

    if comment:
        # update comment
        r = requests.put('https://api.trello.com/1/actions/' + comment.id + '/text/', params={
            'key': os.environ['TRELLO_BOT_API_KEY'],
            'token': os.environ['TRELLO_BOT_TOKEN']
        }, data={'value': raw})
        r.raise_for_status()
    else:
        # create comment
        trello = TrelloApi(os.environ['TRELLO_BOT_API_KEY'], os.environ['TRELLO_BOT_TOKEN'])
        trello.cards.new_action_comment(card.id, unicode(raw, 'utf-8'))

def publish_to_bridgy(silo, board_id, card_id):
    s = select([column('domain'), text('boards.subdomain')])\
        .select_from(
            table('prefs_cards')
                .join(table('boards'), text('boards.subdomain = prefs_cards.subdomain'))
        )\
        .where(text('boards.id = :board_id'))\
        .limit(1)
    row = db.session.execute(s, {'board_id': board_id}).first()
    if not row:
        return

    # prefer the domain if the app is using one, since people would like to publicize their domains
    # instead of something dot websitesfortrello dot com, especially if they are paying.
    domain, subdomain = row
    host = domain if domain else '%s.%s' % (subdomain, os.environ.get('DOMAIN'))

    r = requests.post(
        'https://www.brid.gy/publish/webmention?bridgy_omit_link=true',
        data={
            'source': 'http://%s/c/%s' % (host, card_id),
            'target': 'http://brid.gy/publish/%s' % (silo)
        }
    )
    if r.ok:
        print r.json()
        print r.json().keys()
        card = Card.query.get(card_id)
        card.syndicated.append(r.json()['url'])
        card.syndicated.changed()
        db.session.add(card)
        db.session.commit()
    if not r.ok:
        print 'error while publishing card %s, board %s, to bridgy: %s' \
                % (card_id, board_id, r.json().get('error', r.text))






