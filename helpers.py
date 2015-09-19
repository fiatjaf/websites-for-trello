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
            'subject': 'Do you need help with Websites for Trello?',
            'text': '''
hey {name},

I've seen you tried http://websitesfortrello.com/ some time ago and created a website.

How is your experience going? Maybe have a question or suggestion? I'll be happy if I can help somehow.

If you like Trello as I do, perhaps you prefer to discuss issues and questions inside a Trello board. If that's the case, feel free to add me (fiatjaf) to the board powering your website so we can work together on getting your site in the shape you want it.

Also, if you're more fan of talking than writing, we can schedule a Google Hangouts call for working together in setting up your site. Just say when you would be happy to do it!

In any case, thank you for trying Websites for Trello and good luck!

Giovanni T. Parra
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
