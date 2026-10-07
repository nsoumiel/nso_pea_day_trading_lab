import getpass
import json
import urllib.request

token = getpass.getpass("Token Telegram : ")
url = f"https://api.telegram.org/bot{token}/getUpdates"

with urllib.request.urlopen(url, timeout=15) as response:
    data = json.load(response)

for update in data.get("result", []):
    chat = update.get("message", {}).get("chat", {})
    if chat.get("type") == "private":
        print("Chat ID :", chat["id"])