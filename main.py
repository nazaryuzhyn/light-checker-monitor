import asyncio
import time
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from dotenv import load_dotenv
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PING_TIMEOUT = 60  # 60 секунд без пінгу = світло зникло
DATA_DIR = os.environ.get("DATA_DIR", ".")
USERS_FILE = os.path.join(DATA_DIR, "users.json")


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

bot = None
tg_app = None


# ====== ДОПОМІЖНІ ФУНКЦІЇ ======
def get_status_text():
    if state["power_is_on"]:
        last = datetime.fromtimestamp(state["last_ping"], tz=KYIV_TZ).strftime("%H:%M:%S")
        elapsed = int((time.time() - state["last_ping"]) / 60)
        ago_text = f"\n({elapsed} хв тому)" if elapsed > 0 else ""
        return (
            f"✅ *Світло є.*\n\n"
            f"Останній сигнал: {last}"
            f"{ago_text}"
        )
    else:
        off_time = datetime.fromtimestamp(state["power_off_time"], tz=KYIV_TZ).strftime("%H:%M")
        duration = int((time.time() - state["power_off_time"]) / 60)
        hours = duration // 60
        minutes = duration % 60
        dur_text = f"{hours} год {minutes} хв" if hours > 0 else f"{minutes} хв"
        return (
            f"❌ *Світла немає.*\n\n"
            f"Зникло о: {off_time}\n"
            f"Вже {dur_text} без світла"
        )


BTN_CHECK = "🔍 Перевірити стан"
BTN_DETAILS = "📊 Детальніше"


def get_keyboard():
    return ReplyKeyboardMarkup(
        [[BTN_CHECK, BTN_DETAILS]],
        resize_keyboard=True,
    )


async def notify_all(text: str):
    """Надіслати повідомлення всім підписаним користувачам"""
    for chat_id in subscribed_users.copy():
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
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
        f"{greeting}\n\n🏠 *Моніторинг світла вдома*",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribed_users.discard(chat_id)
    save_users(subscribed_users)
    await update.message.reply_text("🔕 Ти відписаний від сповіщень.\nНапиши /start щоб підписатись знову.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text

    if msg == BTN_CHECK:
        await update.message.reply_text(
            text=get_status_text(),
            parse_mode="Markdown"
        )

    elif msg == BTN_DETAILS:
        last = datetime.fromtimestamp(state["last_ping"], tz=KYIV_TZ).strftime("%d.%m %H:%M:%S")
        status = "✅ Електроенергія є" if state["power_is_on"] else "❌ Електроенергії немає"
        text = (
            f"📊 *Детальна інформація*\n\n"
            f"Стан: {status}\n"
            f"Останній пінг: {last}\n"
        )
        if not state["power_is_on"] and state["power_off_time"]:
            off = datetime.fromtimestamp(state["power_off_time"], tz=KYIV_TZ).strftime("%d.%m %H:%M")
            duration = int((time.time() - state["power_off_time"]) / 60)
            text += f"\nВідключено: {off}\nТривалість: {duration} хв"

        await update.message.reply_text(
            text=text,
            parse_mode="Markdown"
        )


# ====== МОНІТОРИНГ ======
async def monitor_power():
    await asyncio.sleep(15)
    while True:
        await asyncio.sleep(5)
        elapsed = time.time() - state["last_ping"]

        if elapsed > PING_TIMEOUT and state["power_is_on"]:
            state["power_is_on"] = False
            state["power_off_time"] = time.time()
            await notify_all("🔴 *Світло зникло!*\n\nESP перестав виходити на зв'язок. ☹️")

        elif elapsed <= PING_TIMEOUT and not state["power_is_on"]:
            state["power_is_on"] = True
            state["power_on_time"] = time.time()
            duration = int((state["power_on_time"] - state["power_off_time"]) / 60)
            hours = duration // 60
            minutes = duration % 60
            dur_text = f"{hours} год {minutes} хв" if hours > 0 else f"{minutes} хв"
            await notify_all(f"💡 *Світло з'явилось!*\n\nНе було: {dur_text}")


# ====== ІНІЦІАЛІЗАЦІЯ БОТА ======
async def setup_bot():
    global tg_app, bot
    tg_app = Application.builder().token(BOT_TOKEN).build()
    bot = tg_app.bot
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("stop", cmd_stop))
    tg_app.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^({BTN_CHECK}|{BTN_DETAILS})$"), button_handler))
    await tg_app.initialize()
    await tg_app.start()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup_bot()
    asyncio.create_task(monitor_power())
    yield
    if tg_app:
        await tg_app.stop()
        await tg_app.shutdown()


app = FastAPI(lifespan=lifespan)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}


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
