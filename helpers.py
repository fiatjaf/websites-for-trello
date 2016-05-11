import os
import time
import datetime
import requests

def extract_card_cover(cover_id, attachments_list):
    for image in attachments_list:
        if image['id'] == cover_id:
            return image['url']
    return None
