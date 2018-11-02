from peewee import *
import datetime
import json

db = SqliteDatabase('/home/app/telegram_bot_avito/my_database.db')




class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    chat_id = CharField(unique=True)
    links = TextField(default='[]')
    showed_ads = TextField(default='[]')

    def get_links(self):
        try:
            return json.loads(self.links)
        except json.JSONDecodeError:
            return []

    def get_ads(self):
        try:
            return json.loads(self.showed_ads)
        except json.JSONDecodeError:
            return []

def init_db():
    print('init_db')
    db.create_tables([User,])


try:
    u = User.get(User.chat_id == '123')
except OperationalError:
    init_db()
except User.DoesNotExist:
    pass