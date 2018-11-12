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

BOT_TOKEN = '*'

from local_settings import *

loop = asyncio.get_event_loop()

URLS = []

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

HELP = '''
/add LINK  - добавить ссылку с авито со СПИСОКМ ОБЬЯВЛЕНИЙ
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
    if text.startswith('http') and ('avito' in text or 'youla.ru' in text):
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
    
async def main():
    while True:
        await asyncio.sleep(60*5)
        for u in User.select():
            messages_to_send = []
            old_ads = u.get_ads()
            def url_handler(url):
                urls = []
                if 'avito' in url:
                    urls = avito_handler(url)
                elif 'youla.ru' in url:
                    urls = youla_handler(url)
                for ad_link in urls:
                    if len(messages_to_send) > 3:
                        break
                    if 'redirect' in ad_link or md5_from_string(ad_link) in old_ads:
                        continue
                    messages_to_send.append(ad_link)
                    old_ads.append(md5_from_string(ad_link))
            [url_handler(link) for link in u.get_links()]
            u.showed_ads = json.dumps(old_ads)
            u.save()
            if messages_to_send:
               await bot.send_message(u.chat_id, '\n'.join(messages_to_send))


if __name__ == '__main__':
    asyncio.ensure_future(main(), loop=loop)
    executor.start_polling(dp, skip_updates=True,loop=loop)

