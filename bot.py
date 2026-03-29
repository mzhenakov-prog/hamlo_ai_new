import requests
import time
import random
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_KEY")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def get_keyboard():
    return {
        "keyboard": [
            ["🤬 Хамло", "💬 Чат 5"],
            ["📊 Статистика", "🗑 Очистить", "❓ Помощь"]
        ],
        "resize_keyboard": True
    }

PROMPTS = {
    "хамло": "Ты — ХАМЛО. Грубый, саркастичный AI. Отвечай коротко (1 предложение), с матом и сарказмом.",
    "чат5": "Ты — умный, дружелюбный AI. Отвечай развёрнуто (2-4 предложения), понятно, без грубостей."
}

def get_ai(msg, mode):
    if not GROQ_KEY:
        return "Ключ AI не настроен"
    h = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    d = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": PROMPTS[mode]},
            {"role": "user", "content": msg}
        ],
        "temperature": 0.85 if mode == "хамло" else 0.7,
        "max_tokens": 200 if mode == "чат5" else 100
    }
    try:
        r = requests.post(GROQ_URL, json=d, headers=h, timeout=20)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return "Ошибка"
    except:
        return "Ошибка"

def send_msg(cid, txt, k=None):
    try:
        d = {"chat_id": cid, "text": txt}
        if k:
            d["reply_markup"] = k
        requests.post(f"{API}/sendMessage", json=d)
    except:
        pass

def get_updates(off=None):
    p = {"timeout": 25}
    if off:
        p["offset"] = off
    try:
        r = requests.get(f"{API}/getUpdates", params=p)
        return r.json().get("result", [])
    except:
        return []

mode = {}
stat = {}
last = 0
print("🤬 ХАМЛО + 💬 Чат 5 ЗАПУЩЕН")

while True:
    try:
        updates = get_updates(last+1)
        for u in updates:
            last = u["update_id"]
            if "message" in u:
                m = u["message"]
                cid = m["chat"]["id"]
                uid = m["from"]["id"]
                txt = m.get("text", "")
                if not txt:
                    continue
                print(f"📩 {txt[:50]}")
                if uid not in mode:
                    mode[uid] = "хамло"
                if uid not in stat:
                    stat[uid] = 0
                stat[uid] += 1
                
                if txt in ["🤬 Хамло", "Хамло"]:
                    mode[uid] = "хамло"
                    send_msg(cid, "✅ Режим ХАМЛО", get_keyboard())
                elif txt in ["💬 Чат 5", "Чат 5"]:
                    mode[uid] = "чат5"
                    send_msg(cid, "✅ Режим ЧАТ 5", get_keyboard())
                elif txt in ["📊 Статистика", "Статистика"]:
                    send_msg(cid, f"Сообщений: {stat[uid]}", get_keyboard())
                elif txt in ["🗑 Очистить", "Очистить"]:
                    send_msg(cid, "🗑 Очищено", get_keyboard())
                elif txt in ["❓ Помощь", "Помощь"]:
                    send_msg(cid, "🤬 ХАМЛО — грубый\n💬 Чат 5 — умный\n@avgustc", get_keyboard())
                elif txt == "/start":
                    send_msg(cid, "🤬 ХАМЛО — грубый\n💬 Чат 5 — умный\nВыбери режим кнопками!", get_keyboard())
                else:
                    cur = mode.get(uid, "хамло")
                    ans = get_ai(txt, cur)
                    send_msg(cid, ans if ans else "Ошибка", get_keyboard())
        time.sleep(0.5)
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)
