import os
import time
import datetime
import requests
from email import utils

def schedule_welcome_email(user_id, user_email):
    now = datetime.datetime.now()
    inthreedays = now + datetime.timedelta(days=3) - datetime.timedelta(hours=4)
    deliverytime = utils.formatdate(time.mktime(inthreedays.timetuple()))

    r = requests.post('https://api.mailgun.net/v3/websitesfortrello.com/messages',
        auth=('api', os.getenv('MAILGUN_API_KEY')),
        data={
            'from': 'welcome@websitesfortrello.com',
            'to': user_email,
            'subject': 'Feedback request from Websites for Trello',
            'text': '''
hey {name},

I've seen you tried http://websitesfortrello.com/ some time ago and created a website.

Would you care to waste a little of your time to tell us what did you like and what you didn't like? Is there something that you want and we aren't providing?

Anything you say will help us a lot.
Thank you very much for your time and for reading this!

Giovanni T. Parra.
Websites for Trello
            '''.format(name=user_id),
            'h:Reply-To': 'websitesfortrello@boardthreads.com',
            'o:deliverytime': deliverytime
        }
    )
    if r.ok:
        print ':: MODEL-UPDATES :: scheduled email to %s to %s' % (user_id, deliverytime)
    else:
        print r.text

def extract_card_cover(cover_id, attachments_list):
    for image in attachments_list:
        if image['id'] == cover_id:
            return image['url']
    return None
