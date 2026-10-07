import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from .models import UTC


def load_env(path):
    if not os.path.exists(path): return
    with open(path,encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            key, sep, value = line.partition('=')
            if sep: os.environ.setdefault(key.strip(),value.strip().strip('\"').strip("'"))


class Telegram:
    def __init__(self, chat_id):
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID',str(chat_id))
        self.token = os.getenv('TELEGRAM_BOT_TOKEN','')
        if not self.token: raise ValueError('Renseigner TELEGRAM_BOT_TOKEN dans .env')

    def send(self, text):
        req = urllib.request.Request('https://api.telegram.org/bot'+self.token+'/sendMessage',
            data=urllib.parse.urlencode({'chat_id':self.chat_id,'text':text}).encode(),method='POST')
        try:
            with urllib.request.urlopen(req,timeout=15) as r:
                result = json.load(r)
            if not result.get('ok'): raise RuntimeError('Telegram a refusé le message')
        except Exception:
            raise RuntimeError('Échec Telegram : vérifier token, chat_id et réseau (secret masqué)') from None

    def flush(self, store):
        # At-least-once delivery: a lost HTTP acknowledgement can cause a duplicate.
        for key,text in store.db.execute('SELECT key,text FROM notifications WHERE sent IS NULL AND attempts<10 ORDER BY rowid LIMIT 20').fetchall():
            with store.db:
                store.db.execute('UPDATE notifications SET attempts=attempts+1 WHERE key=?',(key,))
            self.send(text)
            with store.db:
                store.db.execute('UPDATE notifications SET sent=? WHERE key=?',(datetime.now(UTC).isoformat(),key))
