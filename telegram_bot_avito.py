from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, executor, types
import requests
import pickle
import urllib
from datetime import datetime,timedelta
import time
import json
import telegram
import time
from contextlib import closing
from models import User
import json
import asyncio
import hashlib
import re

BOT_TOKEN = '*'

from local_settings import *

loop = asyncio.get_event_loop()

URLS = []

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

HELP = '''
/add base_link  - добавить ссылку с авито со СПИСОКМ ОБЬЯВЛЕНИЙ
/all  - показатьвсе что добавлено
/clear - удалить все ссылки
/help - помощь
/delete - удалить ссылку
'''

@dp.message_handler(commands=['clear'])
async def clear(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    user.links = '[]'
    user.save()
    answer = 'Все ссылки удалены'
    await bot.send_message(message.chat.id, answer )


@dp.message_handler(commands=['delete'])
async def delete(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    links = user.get_links()
    text = message.text.replace('/delete ', '')
    remove_links = [x for x in links if len(text) > 3 and text in x]
    user.links = json.dumps([x for x in links if x not in remove_links])
    user.save()
    answer = ', '.join(remove_links) if remove_links else 'Не найдено ссылок с таким именем'
    await bot.send_message(message.chat.id, answer )

@dp.message_handler(commands=['all'])
async def all(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    links = user.get_links()
    answer = ', '.join(links) if links else 'У вас нет ссылок'
    await bot.send_message(message.chat.id, answer )

@dp.message_handler(commands=['add'])
async def add_link(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    links = user.get_links()
    text = message.text.replace('/add ','')
    if text.startswith('http') and ('avito' in text or 'youla.ru' in text or 'cian.ru' in text):
        links.append(text)
        user.links = json.dumps(links)
        user.save()
        answer = 'Ссылка добавлена !'
    else:
        answer = 'Не смог распознать ссылку попробуйте еще раз'
    await bot.send_message(message.chat.id, answer)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        user = User.get(User.chat_id == message.chat.id)
        answer = 'Привет! Я тебя помню.'
    except User.DoesNotExist:
        user = User.create(chat_id=message.chat.id)
        answer = 'Привет! У тебя нет ссылок на авито за которыми ты следишь, отправь первую!'
    await bot.send_message(message.chat.id, answer)
    await bot.send_message(message.chat.id, HELP)


@dp.message_handler(commands=['help'])
async def echo(message: types.Message):
    await bot.send_message(message.chat.id, HELP)



def md5_from_string(source):
    h = hashlib.md5()
    h.update(source.encode())
    return h.hexdigest()


def avito_handler(url):
    res = []
    format_name = lambda x: 'https://www.avito.ru' + x['href']
    format_km = lambda x: ''.join([i for i in x if i.isdigit() or i == '.'])
    soup = BeautifulSoup(requests.get(url, verify=True).text)
    for el in soup.select('div.item_table'):
        ad_link = el.select('div.description h3 a')
        try:
            ad_link = format_name(ad_link[0])
            if 'redirect' in ad_link:
                continue
        except IndexError:
            continue
        res.append(ad_link)
    return res

async def check_walk_distance(url):
    max_distance_km = 2
    def get_distance(el):
        el=el.replace(u'\xa0',u'|')
        try:
            res=re.findall(r'\((.*?)\)',el)[0].split('|')
        except IndexError:
            return False
        return (res[1] == 'м' and float(res[0]) < max_distance_km * 1000) or (res[1] == 'км' and float(res[0]) < max_distance_km)
    ad_page = BeautifulSoup(requests.get(url, verify=True).text)
    items_metro = ad_page.findAll('span',{'class':'item-map-metro'})
    distances = [x for x in items_metro if get_distance(x.text)]
    await asyncio.sleep(20)
    return any(distances)


def cian_handler(url):
    def find(elements,tag,name):
        return [x for x in elements.findAll(tag) if name in ''.join(x.attrs.get('class',''))]

    res = []
    soup = BeautifulSoup(requests.get(url, verify=True).text)
    wrappers = find(soup,'div','wrapper')
    most_big = sorted([(i,len(f.text))for i,f in enumerate(wrappers)],key=lambda x:x[1],reverse=True)[0][0]

    for el in find(wrappers[most_big],'div','card'):
        try:
            ad_link = find(el,'a','header')[0].attrs['href']
        except IndexError:
            continue
        res.append(ad_link)
    return res

def youla_handler(url):
    res = []
    format_name = lambda x: 'https://youla.ru/' + x['href']
    soup = BeautifulSoup(requests.get(url, verify=True).text)
    for el in soup.select('li.product_item'):
        ad_link = el.select('a')
        try:
            res.append(format_name(ad_link[0]))
        except IndexError:
            continue
    return res


def url_handler(url):
    if 'avito' in url:
        return avito_handler(url)
    elif 'youla.ru' in url:
        return youla_handler(url)
    elif 'cian.ru' in url:
        return cian_handler(url)
    return []

async def main():
    print('start')
    while True:
        for u in User.select():
            messages_to_send = []
            old_ads = u.get_ads()
            for base_link in u.get_links():
                for ad_link in url_handler(base_link):
                    if len(messages_to_send) > 3:
                        break
                    if 'redirect' in ad_link or (md5_from_string(ad_link) in old_ads):
                        continue
                    if 'avito' in base_link and 'kvartiry' in ad_link:
                        walk_distance = await check_walk_distance(ad_link)
                        if walk_distance:
                            messages_to_send.append(ad_link)
                    else:
                        messages_to_send.append(ad_link)
                    old_ads.append(md5_from_string(ad_link))
            u.showed_ads = json.dumps(old_ads)
            u.save()
            if messages_to_send:
               await bot.send_message(u.chat_id, '\n'.join(messages_to_send))
        await asyncio.sleep(60*5)


if __name__ == '__main__':
    asyncio.ensure_future(main(), loop=loop)
    executor.start_polling(dp, skip_updates=True,loop=loop)

