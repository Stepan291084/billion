import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = '7724629160:AAFoLnem4PMJGzdHqiZhlMcQl92vCIW-ZnY'
MAIN_ADMIN_ID = 422066107

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        time TEXT,
        date TEXT,
        image TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event_id INTEGER,
        username TEXT
    )
''')
conn.commit()

def main_menu(is_admin=False):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📆 Список событий", callback_data="list_events"),
        InlineKeyboardButton("📅 Календарь", callback_data="calendar")
    )
    if is_admin:
        kb.add(
            InlineKeyboardButton("➕ Добавить", callback_data="add_event"),
            InlineKeyboardButton("📥 Участники", callback_data="participants"),
            InlineKeyboardButton("📤 Экспорт", callback_data="export")
        )
    return kb

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    is_admin = message.from_user.id == MAIN_ADMIN_ID
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu(is_admin))

@dp.callback_query_handler(lambda c: c.data == "list_events")
async def list_events(query: types.CallbackQuery):
    cursor.execute("SELECT id, title, description, time, date FROM events ORDER BY date, time")
    events = cursor.fetchall()
    if not events:
        await query.message.answer("Пока нет запланированных событий.")
        await query.answer()
        return
    is_admin = query.from_user.id == MAIN_ADMIN_ID
    for e in events:
        eid, title, desc, time, date = e
        kb = InlineKeyboardMarkup()
        cursor.execute("SELECT * FROM registrations WHERE user_id=? AND event_id=?", (query.from_user.id, eid))
        reg = cursor.fetchone()
        if reg:
            btn = InlineKeyboardButton("✅ Вы зарегистрированы", callback_data="none", disabled=True)
            kb.add(btn)
        else:
            kb.add(InlineKeyboardButton("✅ Записаться", callback_data=f"reg_{eid}"))
        if is_admin:
            kb.add(InlineKeyboardButton("📋 Список участников", callback_data=f"show_regs_{eid}"))
        await query.message.answer(
            f"📍 {title}\n🕒 {time} | 📅 {date}\n\n{desc}",
            reply_markup=kb
        )
    await query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("show_regs_"))
async def show_regs(query: types.CallbackQuery):
    if query.from_user.id != MAIN_ADMIN_ID:
        await query.answer("Недостаточно прав.")
        return
    eid = int(query.data.split("_")[2])
    cursor.execute("SELECT user_id, username FROM registrations WHERE event_id=?", (eid,))
    regs = cursor.fetchall()
    if not regs:
        await query.message.answer("Никто не зарегистрирован на это событие.")
        await query.answer()
        return
    text = "Список зарегистрированных:\n"
    kb = InlineKeyboardMarkup()
    for user_id, username in regs:
        display = f"{username or user_id}"
        kb.add(
            InlineKeyboardButton(f"❌ {display}", callback_data=f"unreg_{eid}_{user_id}")
        )
        text += f"— {display}\n"
    await query.message.answer(text, reply_markup=kb)
    await query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("unreg_"))
async def admin_unreg(query: types.CallbackQuery):
    if query.from_user.id != MAIN_ADMIN_ID:
        await query.answer("Недостаточно прав.")
        return
    _, eid, uid = query.data.split("_")
    cursor.execute("DELETE FROM registrations WHERE event_id=? AND user_id=?", (eid, uid))
    conn.commit()
    await query.answer("Регистрация отменена!", show_alert=True)
    await query.message.answer(f"Регистрация пользователя {uid} на событие {eid} отменена.")

@dp.callback_query_handler(lambda c: c.data == "calendar")
async def calendar_view(query: types.CallbackQuery):
    cursor.execute("SELECT DISTINCT date FROM events ORDER BY date")
    dates = cursor.fetchall()
    if not dates:
        await query.message.answer("Пока нет запланированных событий.")
        await query.answer()
        return
    text = "Выбери дату:\n" + "\n".join([d[0] for d in dates])
    await query.message.answer(text)
    await query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("reg_"))
async def register(query: types.CallbackQuery):
    eid = int(query.data.split("_")[1])
    uid = query.from_user.id
    username = query.from_user.username or ""
    cursor.execute("SELECT * FROM registrations WHERE user_id=? AND event_id=?", (uid, eid))
    if cursor.fetchone():
        await query.answer("Вы уже зарегистрированы!", show_alert=True)
    else:
        cursor.execute("INSERT INTO registrations (user_id, event_id, username) VALUES (?, ?, ?)", (uid, eid, username))
        conn.commit()
        await query.answer("Вы успешно зарегистрированы!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "add_event")
async def add_event_cb(query: types.CallbackQuery):
    if query.from_user.id != MAIN_ADMIN_ID:
        await query.answer("Недостаточно прав.")
        return
    await query.message.answer("Отправьте событие в формате:\nНазвание | Описание | Время | Дата (ДД.ММ.ГГГГ)")
    await query.answer()

@dp.message_handler(lambda message: message.text and "|" in message.text and message.from_user.id == MAIN_ADMIN_ID)
async def process_event(message: types.Message):
    try:
        title, desc, time, date = map(str.strip, message.text.split("|"))
        cursor.execute(
            "INSERT INTO events (title, description, time, date) VALUES (?, ?, ?, ?)",
            (title, desc, time, date)
        )
        conn.commit()
        await message.answer("Событие добавлено!")
    except Exception as e:
        await message.answer(f"Ошибка добавления: {e}")

@dp.callback_query_handler(lambda c: c.data == "participants")
async def show_participants(query: types.CallbackQuery):
    cursor.execute("SELECT id, title FROM events")
    data = cursor.fetchall()
    msg = "🧾 Регистрации:\n"
    for eid, title in data:
        cursor.execute("SELECT COUNT(*) FROM registrations WHERE event_id=?", (eid,))
        count = cursor.fetchone()[0]
        msg += f"{title} — {count} регистраций\n"
    await query.message.answer(msg)
    await query.answer()

@dp.callback_query_handler(lambda c: c.data == "export")
async def export_excel(query: types.CallbackQuery):
    import xlsxwriter
    filename = "registrations.xlsx"
    workbook = xlsxwriter.Workbook(filename)
    sheet = workbook.add_worksheet()

    sheet.write(0, 0, "Event ID")
    sheet.write(0, 1, "Event Name")
    sheet.write(0, 2, "User ID")
    sheet.write(0, 3, "Username")

    cursor.execute("""
        SELECT registrations.event_id, events.title, registrations.user_id, registrations.username
        FROM registrations
        JOIN events ON registrations.event_id = events.id
    """)
    rows = cursor.fetchall()
    for idx, (event_id, event_name, user_id, username) in enumerate(rows, start=1):
        sheet.write(idx, 0, event_id)
        sheet.write(idx, 1, event_name)
        sheet.write(idx, 2, user_id)
        sheet.write(idx, 3, username if username else "")
    workbook.close()
    await bot.send_document(query.message.chat.id, open(filename, "rb"))
    await query.answer()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
