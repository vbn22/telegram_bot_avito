import asyncio
import hashlib
import json
import re
import urllib

import requests
from aiogram import Bot, Dispatcher, executor, types
from bs4 import BeautifulSoup

from models import User

rom
urllib.parse
import urlparse

BOT_TOKEN = '*'


def bs4_handler(url):
    print(url)
    return BeautifulSoup(requests.get(url, verify=True).text, "html.parser")


class Ad(object):
    max_distance_m = 2 * 1000
    skip = False
    need_sleep = False
    add_message = ''
    __body = None

    def __init__(self, url, base_link):
        self.url = url
        self.base_link = base_link
        self.md5 = self.md5_from_string(url)

        if 'avito' in self.base_link and 'kvartiry' in self.url:
            walk_distances = self.walk_distances()
            if not any(walk_distances):
                self.skip = True
            else:
                self.add_message = f'{self.price_per_meter} {min(walk_distances)}'

    @property
    def body(self):
        if not self.__body:
            self.__body = bs4_handler(self.url)
            self.need_sleep = True
        return self.__body

    @property
    def price(self):
        try:
            return float(self.body.findAll('span', {'itemprop': 'price'})[0].text.replace(' ', ''))
        except (IndexError, ValueError):
            print('price')
            return 0

    @property
    def area(self):
        try:
            text = \
                [x.text for x in self.body.findAll('li', {'class': 'item-params-list-item'}) if
                 'Общая площадь' in x.text][
                    0]
            return float(text.replace(u'\xa0', u'|').replace(': ', '|').split('|')[1])
        except (IndexError, ValueError):
            print('area')
            return 0

    @property
    def price_per_meter(self):
        try:
            price, area = self.price, self.area
            return int(price / area)
        except ValueError:
            print('price_per_meter')
            return 0

    def get_distance(self, el):
        el = el.replace(u'\xa0', u'|')
        try:
            res = re.findall(r'\((.*?)\)', el)[0].split('|')
        except IndexError:
            return 0
        distance = float(res[0])
        if res[1] == 'км':
            distance = distance * 1000
        return distance

    def walk_distances(self):
        items_metro = self.body.findAll('span', {'class': 'item-map-metro'})
        distances = [self.get_distance(x.text) for x in items_metro]
        return [d for d in distances if d and d < self.max_distance_m]

    @staticmethod
    def md5_from_string(source):
        h = hashlib.md5()
        h.update(source.encode())
        return h.hexdigest()

    @property
    def message(self):
        return f'{self.url} {self.add_message}'


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
    await bot.send_message(message.chat.id, answer)


@dp.message_handler(commands=['delete'])
async def delete(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    links = user.get_links()
    text = message.text.replace('/delete ', '')
    remove_links = [x for x in links if len(text) > 3 and text in x]
    user.links = json.dumps([x for x in links if x not in remove_links])
    user.save()
    answer = ', '.join(remove_links) if remove_links else 'Не найдено ссылок с таким именем'
    await bot.send_message(message.chat.id, answer)


@dp.message_handler(commands=['all'])
async def all(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    links = user.get_links()
    answer = ', '.join(links) if links else 'У вас нет ссылок'
    await bot.send_message(message.chat.id, answer)


@dp.message_handler(commands=['add'])
async def add_link(message: types.Message):
    user = User.get(User.chat_id == message.chat.id)
    links = user.get_links()
    text = message.text.replace('/add ', '')
    if text.startswith('http'):
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
        answer = 'Привет! У тебя нет ссылок за которыми ты следишь, отправь первую!'
    await bot.send_message(message.chat.id, answer)
    await bot.send_message(message.chat.id, HELP)


@dp.message_handler(commands=['help'])
async def echo(message: types.Message):
    await bot.send_message(message.chat.id, HELP)


def avito_handler(url):
    res = []
    format_name = lambda x: 'https://www.avito.ru' + x['href']
    format_km = lambda x: ''.join([i for i in x if i.isdigit() or i == '.'])
    soup = bs4_handler(url)
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


def cian_handler(url):
    def find(elements, tag, name):
        return [x for x in elements.findAll(tag) if name in ''.join(x.attrs.get('class', ''))]

    res = []
    soup = bs4_handler(url)
    wrappers = find(soup, 'div', 'wrapper')
    try:
        most_big = sorted([(i, len(f.text)) for i, f in enumerate(wrappers)], key=lambda x: x[1], reverse=True)[0][0]
    except IndexError:
        return res

    for el in find(wrappers[most_big], 'div', 'card'):
        try:
            ad_link = find(el, 'a', 'header')[0].attrs['href']
        except IndexError:
            continue
        res.append(ad_link)
    return res


def youla_handler(url):
    res = []
    format_name = lambda x: 'https://youla.ru/' + x['href']
    soup = bs4_handler(url)
    for el in soup.select('li.product_item'):
        ad_link = el.select('a')
        try:
            res.append(format_name(ad_link[0]))
        except IndexError:
            continue
    return res


def domofond_handler(url):
    format_name = lambda x: f'https://www.domofond.ru{x}'
    soup = bs4_handler(url)
    filter_el = lambda x: list(filter(lambda p: 'long-item' in p, x.attrs.get('class', [])))
    return [format_name(el.attrs.get('href', '')) for el in soup.select('a') if filter_el(el)]


def ebay_handler(url):
    session = requests.Session()
    base_url = 'https://www.ebay.com/gh/setuserpreference?correlation=si%3Dbd0004d71830ab8ca93c7011fffeef9f%2Csiid%3DA' \
               'pOUwcTk*%2Cc%3D163%2Csid%3Dp2481888%2CoperationId%3D2481888%2Ctrk-gflgs%3DAAE*&v=2'
    session.post(base_url, data={"userPreferedCountry": "USA"})
    soup = BeautifulSoup(session.get(url, verify=True).text, "html.parser")
    links = []
    for el in soup.select('li.s-item'):
        time_left = el.select('span.s-item__time--urgent span.s-item__time-left')
        if not time_left:
            continue
        time = re.findall(r'(.*?)m\sleft', time_left[0].text) or re.findall(r'Осталось\s(.*?)\sмин', time_left[0].text)
        if not time:
            continue
        parse_url = urlparse(el.select('a.s-item__link')[0]['href'])
        links.append(f'{parse_url.scheme}://{parse_url.hostname}/{parse_url.path}')
    return links


def url_handler(url):
    if 'avito' in url:
        return avito_handler(url)
    elif 'youla.ru' in url:
        return youla_handler(url)
    elif 'cian.ru' in url:
        return cian_handler(url)
    elif 'domofond' in url:
        return domofond_handler(url)
    elif 'ebay' in url:
        return ebay_handler(url)
    return []


async def main():
    print('start')
    while True:
        for u in User.select():
            ads = []
            old_ads = u.get_ads()
            for base_link in u.get_links():
                # if not ('avito' in base_link and 'kvartiry' in base_link):
                #    print(base_link,'continue')
                #    continue
                # print(base_link)
                for ad_link in url_handler(base_link):
                    ad = Ad(ad_link, base_link)
                    # print(ad.need_sleep)
                    if ad.need_sleep:
                        await asyncio.sleep(7)
                    if len(ads) > 3:
                        break
                    if 'redirect' in ad.url or (ad.md5 in old_ads) or ad.skip:
                        continue
                    ads.append(ad)
                    old_ads.append(ad.md5)
                await asyncio.sleep(7)
            u.showed_ads = json.dumps(old_ads)
            u.save()
            if ads:
                await bot.send_message(u.chat_id, '\n'.join([a.message for a in ads]))
        await asyncio.sleep(60 * 10)


if __name__ == '__main__':
    asyncio.ensure_future(main(), loop=loop)
    executor.start_polling(dp, skip_updates=True, loop=loop)
