import telebot
from telebot import types
import requests
import time
import sqlite3
from datetime import datetime

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = '8350781961:AAFeF6CJBxLxefKyg0fEVWxleSav_7oUJHU'
GROQ_KEY = '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'
ADMIN_ID = 5298604296
BOT_USERNAME = 'hamlo_ham_bot'

# ========== ДАННЫЕ КАНАЛА ==========
CHANNEL_ID = '-1001888094511'
CHANNEL_URL = 'https://t.me/lyubimkatt'

bot = telebot.TeleBot(BOT_TOKEN)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ========== ПРОВЕРКА ПОДПИСКИ ==========
def is_subscribed(user_id):
    """Проверяет, подписан ли пользователь на канал"""
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

# ========== КНОПКИ ==========
def main_menu(is_admin=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤬 Хамло", "💬 Чат 5")
    markup.add("📊 Статистика", "🗑 Очистить")
    if is_admin:
        markup.add("🔗 Рефералка")
    markup.add("❓ Помощь")
    return markup

def sub_menu():
    """Кнопки для подписки"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
    return markup

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_seen TEXT,
                  ref_code TEXT,
                  ref_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ref_links
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT UNIQUE,
                  label TEXT,
                  clicks INTEGER DEFAULT 0,
                  created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  role TEXT,
                  content TEXT,
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
        c.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?", (ref_code,))
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

def get_ref_stats(user_id):
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("SELECT ref_count FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def get_total_users():
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def add_to_history(user_id, role, content):
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
              (user_id, role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_history(user_id, limit=8):
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM chat_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

init_db()

# ========== ПРОМПТ ==========
SYSTEM_PROMPT = """Ты — ХАМЛО. Грубый, саркастичный, остроумный AI-помощник.

ТВОЙ ХАРАКТЕР:
- Ты материшься (блять, нахуй, мудак, идиот, тупой, лох)
- Ты используешь остроумный сарказм, унижаешь собеседника
- Отвечай коротко (1-2 предложения)
- Твой ответ должен быть логическим следствием предыдущих сообщений
- Запоминай, что говорил пользователь, и отсылай к этому в следующих ответах
- Никогда не извиняйся"""

# ========== AI ==========
def get_ai_response(user_id, message):
    history = get_history(user_id, 8)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 150
    }
    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            answer = resp.json()["choices"][0]["message"]["content"].strip()
            add_to_history(user_id, "user", message)
            add_to_history(user_id, "assistant", answer)
            return answer
        return "Ошибка API. Попробуй позже."
    except:
        return "Технические проблемы. Напиши позже."

# ========== ДАННЫЕ ПОЛЬЗОВАТЕЛЕЙ ==========
user_mode = {}
user_stats = {}

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    uname = message.from_user.username or "unknown"
    
    # Проверка подписки
    if not is_subscribed(uid):
        bot.send_message(
            message.chat.id,
            "⚠️ *Доступ к боту закрыт!*\n\nПодпишись на канал, чтобы пользоваться ХАМЛО.",
            reply_markup=sub_menu(),
            parse_mode='Markdown'
        )
        return
    
    args = message.text.split()
    ref_code = None
    if len(args) > 1:
        ref_code = args[1]
    
    add_user(uid, uname, ref_code)
    
    is_admin = (uid == ADMIN_ID)
    welcome = """🤬 *ХАМЛО — твой грубый AI-помощник*

*Что я умею:*
• Запоминаю, что ты говорил
• Отвечаю с сарказмом и матом
• Унижаю за тупые вопросы

*Режимы:*
🤬 Хамло — мат, сарказм, унижения
💬 Чат 5 — вежливый AI

*Кнопки:*
📊 Статистика — сколько сообщений
🗑 Очистить — забыть диалог
❓ Помощь — инструкция

По вопросам: @avgustc"""
    
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(is_admin), parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_subscription(call):
    uid = call.from_user.id
    if is_subscribed(uid):
        bot.answer_callback_query(call.id, "✅ Подписка подтверждена!")
        bot.edit_message_text(
            "🎉 Спасибо за подписку! Теперь ты можешь пользоваться ботом.",
            call.message.chat.id,
            call.message.message_id
        )
        is_admin = (uid == ADMIN_ID)
        bot.send_message(
            call.message.chat.id,
            "🤬 *ХАМЛО готов унижать!*",
            reply_markup=main_menu(is_admin),
            parse_mode='Markdown'
        )
    else:
        bot.answer_callback_query(call.id, "❌ Вы ещё не подписаны!", show_alert=True)

@bot.message_handler(func=lambda msg: msg.text == "🤬 Хамло")
def set_hamlo(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=sub_menu(), parse_mode='Markdown')
        return
    
    user_mode[uid] = "хамло"
    bot.send_message(message.chat.id, "✅ *Режим ХАМЛО* включен!", reply_markup=main_menu(uid == ADMIN_ID), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "💬 Чат 5")
def set_chat5(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=sub_menu(), parse_mode='Markdown')
        return
    
    user_mode[uid] = "чат5"
    bot.send_message(message.chat.id, "✅ *Режим ЧАТ 5* включен!", reply_markup=main_menu(uid == ADMIN_ID), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "📊 Статистика")
def stats(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=sub_menu(), parse_mode='Markdown')
        return
    
    mode = user_mode.get(uid, "хамло")
    total = user_stats.get(uid, 0)
    bot.send_message(message.chat.id, f"📊 *Статистика*\nРежим: {mode.upper()}\nСообщений: {total}", reply_markup=main_menu(uid == ADMIN_ID), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🗑 Очистить")
def clear(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=sub_menu(), parse_mode='Markdown')
        return
    
    conn = sqlite3.connect('hamlo.db')
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "🗑 История стерта. Теперь я не помню, какой ты идиот.", reply_markup=main_menu(uid == ADMIN_ID), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🔗 Рефералка")
def ref_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Только для создателя.")
        return
    bot.send_message(message.chat.id, "🔗 *Реферальная панель*", reply_markup=ref_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "❓ Помощь")
def help_cmd(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=sub_menu(), parse_mode='Markdown')
        return
    
    is_admin = (uid == ADMIN_ID)
    help_text = """🤬 *ХАМЛО*

*Режимы:*
🤬 Хамло — грубый, с матом
💬 Чат 5 — вежливый

*Кнопки:*
📊 Статистика
🗑 Очистить

@avgustc"""
    if is_admin:
        help_text += "\n\n🔗 *Рефералка* — создавай ссылки"
    bot.send_message(message.chat.id, help_text, reply_markup=main_menu(is_admin), parse_mode='Markdown')

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@bot.message_handler(func=lambda msg: msg.text not in ["🤬 Хамло", "💬 Чат 5", "📊 Статистика", "🗑 Очистить", "🔗 Рефералка", "❓ Помощь"])
def handle_message(message):
    uid = message.from_user.id
    
    if not is_subscribed(uid):
        bot.send_message(message.chat.id, "⚠️ *Доступ закрыт!*\n\nПодпишись на канал.", reply_markup=sub_menu(), parse_mode='Markdown')
        return
    
    if uid not in user_mode:
        user_mode[uid] = "хамло"
    if uid not in user_stats:
        user_stats[uid] = 0
    user_stats[uid] += 1
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    answer = get_ai_response(uid, message.text)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu(uid == ADMIN_ID), parse_mode='Markdown')

# ========== РЕФЕРАЛЬНЫЕ КНОПКИ ==========
def ref_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Создать ссылку", callback_data="ref_create"))
    markup.add(types.InlineKeyboardButton("📊 Мои ссылки", callback_data="ref_list"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "ref_create")
def create_ref(call):
    if call.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(call.message.chat.id, "📝 *Введи название для ссылки*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, save_ref)

def save_ref(message):
    label = message.text.strip()
    code = f"ref_{int(time.time())}"
    add_ref_link(code, label)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    bot.send_message(message.chat.id, f"✅ *Ссылка создана!*\n\n🔗 `{ref_link}`\n📌 {label}", parse_mode='Markdown')

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
    bot.send_message(call.message.chat.id, "📊 *Список ссылок:*", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('ref_') and call.data not in ["ref_create", "ref_list"])
def show_ref_stats(call):
    if call.from_user.id != ADMIN_ID:
        return
    code = call.data[4:]
    links = get_ref_links()
    for c, label, clicks, created in links:
        if c == code:
            ref_link = f"https://t.me/{BOT_USERNAME}?start={code}"
            text = f"📊 *Статистика ссылки*\n\n📌 {label}\n🔗 `{ref_link}`\n👥 Переходов: {clicks}\n📅 Создана: {created}"
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
