import asyncio
import time
import os
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
PING_TIMEOUT = 300  # 5 хвилин без пінгу = світло зникло
USERS_FILE = "users.json"

# ====== ЗБЕРЕЖЕННЯ КОРИСТУВАЧІВ ======
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_users(users: set):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

subscribed_users = load_users()

# ====== СТАН ======
state = {
    "last_ping": time.time(),
    "power_is_on": True,
    "power_off_time": None,
    "power_on_time": None,
}

bot = Bot(token=BOT_TOKEN)

# ====== ДОПОМІЖНІ ФУНКЦІЇ ======
def get_status_text():
    if state["power_is_on"]:
        last = datetime.fromtimestamp(state["last_ping"]).strftime("%H:%M:%S")
        elapsed = int((time.time() - state["last_ping"]) / 60)
        return (
            f"✅ *Світло є*\n"
            f"Останній сигнал від ESP: {last}\n"
            f"({elapsed} хв тому)"
        )
    else:
        off_time = datetime.fromtimestamp(state["power_off_time"]).strftime("%H:%M")
        duration = int((time.time() - state["power_off_time"]) / 60)
        hours = duration // 60
        minutes = duration % 60
        dur_text = f"{hours} год {minutes} хв" if hours > 0 else f"{minutes} хв"
        return (
            f"❌ *Світла немає*\n"
            f"Зникло о: {off_time}\n"
            f"Вже {dur_text} без світла"
        )

def get_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Перевірити стан", callback_data="check")],
        [InlineKeyboardButton("📊 Детальніше", callback_data="details")],
    ])

async def notify_all(text: str):
    """Надіслати повідомлення всім підписаним користувачам"""
    for chat_id in subscribed_users.copy():
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=get_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            # Якщо користувач заблокував бота — видаляємо зі списку
            print(f"Помилка надсилання до {chat_id}: {e}")
            subscribed_users.discard(chat_id)
            save_users(subscribed_users)

# ====== ОБРОБНИКИ КОМАНД ======
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    is_new = chat_id not in subscribed_users

    subscribed_users.add(chat_id)
    save_users(subscribed_users)

    greeting = "👋 Вітаю! Ти підписаний на сповіщення про світло." if is_new else "👋 Ти вже підписаний!"

    await update.message.reply_text(
        f"{greeting}\n\n🏠 *Моніторинг світла вдома*\nОберіть дію:",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribed_users.discard(chat_id)
    save_users(subscribed_users)
    await update.message.reply_text("🔕 Ти відписаний від сповіщень.\nНапиши /start щоб підписатись знову.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check":
        await query.edit_message_text(
            text=get_status_text(),
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

    elif query.data == "details":
        last = datetime.fromtimestamp(state["last_ping"]).strftime("%d.%m %H:%M:%S")
        status = "✅ Є" if state["power_is_on"] else "❌ Немає"
        text = (
            f"📊 *Детальна інформація*\n\n"
            f"Стан: {status}\n"
            f"Останній пінг: {last}\n"
            f"Таймаут: {PING_TIMEOUT // 60} хв\n"
            f"Підписників: {len(subscribed_users)}"
        )
        if not state["power_is_on"] and state["power_off_time"]:
            off = datetime.fromtimestamp(state["power_off_time"]).strftime("%d.%m %H:%M")
            duration = int((time.time() - state["power_off_time"]) / 60)
            text += f"\nВідключено о: {off}\nТривалість: {duration} хв"

        await query.edit_message_text(
            text=text,
            reply_markup=get_keyboard(),
            parse_mode="Markdown"
        )

# ====== МОНІТОРИНГ ======
async def monitor_power():
    await asyncio.sleep(15)
    while True:
        await asyncio.sleep(30)
        elapsed = time.time() - state["last_ping"]

        if elapsed > PING_TIMEOUT and state["power_is_on"]:
            state["power_is_on"] = False
            state["power_off_time"] = time.time()
            await notify_all("🔴 *Світло зникло!*\nESP перестав виходити на зв'язок.")

        elif elapsed <= PING_TIMEOUT and not state["power_is_on"]:
            state["power_is_on"] = True
            state["power_on_time"] = time.time()
            duration = int((state["power_on_time"] - state["power_off_time"]) / 60)
            hours = duration // 60
            minutes = duration % 60
            dur_text = f"{hours} год {minutes} хв" if hours > 0 else f"{minutes} хв"
            await notify_all(f"💡 *Світло з'явилось!*\nНе було: {dur_text}")

tg_app = None

async def run_bot():
    global tg_app
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("stop", cmd_stop))
    tg_app.add_handler(CallbackQueryHandler(button_handler))
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(monitor_power())
    asyncio.create_task(run_bot())
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/ping")
async def ping():
    state["last_ping"] = time.time()
    return {"status": "ok"}

@app.get("/status")
async def status():
    return {
        "power_is_on": state["power_is_on"],
        "last_ping_ago_seconds": int(time.time() - state["last_ping"]),
        "subscribers": len(subscribed_users)
    }
