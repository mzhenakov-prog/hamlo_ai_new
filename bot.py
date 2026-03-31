import telebot
from telebot import types
import requests
import time
import sqlite3
from datetime import datetime

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = '8347775737:AAFSFwXxse-7c3SsOu4JSTN7jSfdYh4vJa4'
GROQ_KEY = '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'
ADMIN_ID = 5298604296  # Твой ID
CHANNEL_ID = '-1001888094511'
CHANNEL_URL = 'https://t.me/lyubimkatt'
BOT_USERNAME = 'hamlo_ham_bot'  # Username твоего бота

bot = telebot.TeleBot(BOT_TOKEN)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_seen TEXT,
                  ref_code TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ref_links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT UNIQUE,
                  label TEXT,
                  clicks INTEGER DEFAULT 0,
                  created_at TEXT)''')
    conn.commit()
    conn.close()

def add_user(user_id, username, ref_code=None):
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_seen, ref_code) VALUES (?, ?, ?, ?)",
              (user_id, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ref_code))
    if ref_code:
        c.execute("UPDATE ref_links SET clicks = clicks + 1 WHERE code = ?", (ref_code,))
    conn.commit()
    conn.close()

def add_ref_link(code, label):
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("INSERT INTO ref_links (code, label, created_at) VALUES (?, ?, ?)",
              (code, label, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def get_ref_links():
    conn = sqlite3.connect('hamlo.db')
    rows = conn.execute("SELECT code, label, clicks, created_at FROM ref_links ORDER BY id DESC").fetchall()
    conn.close()
    return rows

def delete_ref_link(code):
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("DELETE FROM ref_links WHERE code = ?", (code,))
    conn.commit()
    conn.close()

init_db()

# ========== ПРОВЕРКА ПОДПИСКИ ==========
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# ========== РЕЖИМЫ ==========
MODES = {
    "хамло": """Ты — ХАМЛО. Грубый, саркастичный AI-помощник.
Отвечай коротко (1 предложение), с матом и сарказмом.
Используй слова: блять, нахуй, мудак, идиот, тупой.
Никогда не извиняйся. Унижай за нытьё и тупые вопросы.""",

    "чат5": """Ты — умный, дружелюбный AI-помощник.
Отвечай развёрнуто (2-3 предложения), понятно, с юмором.
Без мата и грубостей. Помогай решать вопросы."""
}

user_mode = {}
user_stats = {}

# ========== КНОПКИ ==========
def main_menu(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤬 Хамло", "💬 Чат 5")
    markup.add("📊 Статистика", "🗑 Очистить")
    if is_admin:
        markup.add("🔗 Рефералка")
    markup.add("❓ Помощь")
    return markup

def ref_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Создать ссылку", callback_data="ref_create"))
    markup.add(types.InlineKeyboardButton("📊 Мои ссылки", callback_data="ref_list"))
    return markup

# ========== AI ==========
def get_ai(message, mode):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": MODES[mode]},
            {"role": "user", "content": message}
        ],
        "temperature": 0.85,
        "max_tokens": 150
    }
    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        return "Ошибка API. Попробуй позже."
    except:
        return "Технические проблемы. Напиши позже."

def fallback_hamlo(t):
    tl = t.lower()
    if "привет" in tl: return "О, ещё один идиот. Чего припёрся?"
    if "как дела" in tl: return "Тебе-то какое дело, мудила?"
    return "Чё, язык проглотил?"

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.username or "unknown"
    
    # Реферальный код
    args = message.text.split()
    ref_code = None
    if len(args) > 1:
        ref_code = args[1]
    
    add_user(uid, uname, ref_code)
    
    # Проверка подписки
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(
            message.chat.id,
            "⚠️ *Доступ к боту закрыт!*\n\nПодпишись на канал, чтобы пользоваться ХАМЛО.",
            reply_markup=markup,
            parse_mode='Markdown'
        )
        return
    
    if uid not in user_mode:
        user_mode[uid] = "хамло"
    if uid not in user_stats:
        user_stats[uid] = 0
    user_stats[uid] += 1
    
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, "🤬 *ХАМЛО готов унижать!*\n\nВыбери режим кнопками.", 
                     reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🤬 Хамло")
def set_hamlo(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    user_mode[uid] = "хамло"
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, "✅ *Режим ХАМЛО* включен!", 
                     reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "💬 Чат 5")
def set_chat5(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    user_mode[uid] = "чат5"
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, "✅ *Режим ЧАТ 5* включен!", 
                     reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "📊 Статистика")
def stats(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    mode = user_mode.get(uid, "хамло")
    total = user_stats.get(uid, 0)
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, f"📊 *Статистика*\nРежим: {mode.upper()}\nСообщений: {total}", 
                     reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🗑 Очистить")
def clear(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, "🗑 История стерта.", 
                     reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🔗 Рефералка")
def ref_cmd(message):
    uid = message.from_user.id
    if uid != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Только для создателя.")
        return
    
    bot.send_message(message.chat.id, "🔗 *Реферальная панель*", reply_markup=ref_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "❓ Помощь")
def help_cmd(message):
    uid = message.from_user.id
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    is_admin = (uid == ADMIN_ID)
    help_text = """🤬 *ХАМЛО — грубый AI-бот*

*Режимы:*
🤬 Хамло — мат, унижения, сарказм
💬 Чат 5 — умный и вежливый

*Кнопки:*
📊 Статистика — счётчик
🗑 Очистить — забыть диалог"""

    if is_admin:
        help_text += "\n\n🔗 *Рефералка* — создавай ссылки для рекламы"
    
    help_text += "\n\n@avgustc"
    
    bot.send_message(message.chat.id, help_text, reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text not in ["🤬 Хамlo", "💬 Чат 5", "📊 Статистика", "🗑 Очистить", "🔗 Рефералка", "❓ Помощь"])
def handle_message(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
        markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*", reply_markup=markup, parse_mode='Markdown')
        return
    
    mode = user_mode.get(uid, "хамло")
    
    if uid not in user_stats:
        user_stats[uid] = 0
    user_stats[uid] += 1
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    answer = get_ai(message.text, mode)
    if not answer or "Ошибка" in answer:
        if mode == "хамло":
            answer = fallback_hamlo(message.text)
        else:
            answer = "Не могу ответить сейчас. Попробуй позже."
    
    is_admin = (uid == ADMIN_ID)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu(is_admin), parse_mode='Markdown')

# ========== ПРОВЕРКА ПОДПИСКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_callback(call):
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
        bot.edit_message_text(
            "🎉 Спасибо за подписку! Теперь ты можешь пользоваться ботом.",
            call.message.chat.id,
            call.message.message_id
        )
        uid = call.from_user.id
        is_admin = (uid == ADMIN_ID)
        bot.send_message(
            call.message.chat.id,
            "🤬 *ХАМЛО готов унижать!*",
            reply_markup=main_menu(is_admin),
            parse_mode='Markdown'
        )
    else:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписаны!", show_alert=True)

# ========== РЕФЕРАЛЬНЫЕ КНОПКИ ==========
@bot.callback_query_handler(func=lambda call: call.data == "ref_create")
def create_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(call.message.chat.id, "📝 *Введи название для ссылки*\n\nНапример: `канал_петрова`", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_ref)

def save_ref(message):
    label = message.text.strip()
    code = f"ref_{int(time.time())}"
    add_ref_link(code, label)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    bot.send_message(message.chat.id, f"✅ *Ссылка создана!*\n\n🔗 `{ref_link}`\n📌 Метка: {label}", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "ref_list")
def list_refs(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    links = get_ref_links()
    if not links:
        bot.send_message(call.message.chat.id, "📭 *Нет созданных ссылок*", parse_mode='Markdown')
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for code, label, clicks, created in links:
        markup.add(types.InlineKeyboardButton(f"📊 {label} — {clicks} переходов", callback_data=f"ref_{code}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_ref"))
    
    bot.send_message(call.message.chat.id, "📊 *Список реферальных ссылок:*", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('ref_') and call.data != "ref_create" and call.data != "ref_list")
def show_ref_stats(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    code = call.data[4:]
    links = get_ref_links()
    for c, label, clicks, created in links:
        if c == code:
            ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
            text = f"📊 *Статистика ссылки*\n\n📌 Метка: {label}\n🔗 `{ref_link}`\n👥 Переходов: {clicks}\n📅 Создана: {created}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🗑 Удалить", callback_data=f"del_{code}"))
            markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="ref_list"))
            bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode='Markdown')
            bot.delete_message(call.message.chat.id, call.message.message_id)
            return

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_'))
def delete_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    code = call.data[4:]
    delete_ref_link(code)
    bot.answer_callback_query(call.id, "✅ Ссылка удалена!")
    bot.edit_message_text("🗑 Ссылка удалена", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_ref")
def back_to_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    bot.delete_message(call.message.chat.id, call.message.message_id)
    ref_cmd(call.message)

if __name__ == '__main__':
    print("🤬 ХАМЛО запущен!")
    bot.infinity_polling()
