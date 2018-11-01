# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import requests
import pickle
import urllib
from datetime import datetime,timedelta
import time
import json
import telegram



BOT_TOKEN = '*'

from local_settings import *



URLS = []

def start(urls = URLS):
    
    try:
        old_links = pickle.load(open( "links.p", "rb" ))
    except:
        old_links = []

    format_name = lambda x:'https://www.avito.ru'+x['href']
    format_km = lambda x:''.join([i for i in x if i.isdigit() or i == '.'])
    messages_to_send = []

    def url_handler(url):
        soup = BeautifulSoup(requests.get(url,verify=True).text)
        for el in soup.select('div.item_table'):
            link = el.select('div.description h3 a')
            if not link or format_name(link[0]) in old_links or 'redirect' in format_name(link[0]):
                continue
            messages_to_send.append(format_name(link[0]))

    [url_handler(url) for url in urls]
    if not messages_to_send:
        return old_links
    
    messages_to_send = messages_to_send[:10]
    bot = telegram.Bot(BOT_TOKEN)
    bot.send_message(137949293,'\n'.join(messages_to_send))
    [old_links.append(link) for link in messages_to_send]

    pickle.dump(old_links, open( "links.p", "wb" ) )
    return old_links


if __name__ == '__main__':
    start()

