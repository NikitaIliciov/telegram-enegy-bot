import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import asyncio
import functools

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

BOT_TOKEN = '7351921078:AAGw37UR1PUAutFaksH0xTpBo4T92x9czVk'
user_sectors = {}  # ✅ Stocăm utilizatorii și sectorul ales
CHAT_ID = 422939473  # Fără ghilimele – ca int
all_users = {}  # set pentru toți userii

SECTOARE = [
    "Chişinău, sectorul Botanica",
    "Chişinău, sectorul Ciocana",
    "Chişinău, sectorul Centru",
    "Chişinău, sectorul Bubuieci",
    "Chişinău, sectorul Rîșcani"
]

def get_tomorrow_url():
    tomorrow = datetime.now() + timedelta(days=1)
    date_str = tomorrow.strftime("%Y-%m-%d")
    print(f"[DEBUG] Data pentru URL: {date_str}")
    return f'https://www.premierenergydistribution.md/ro/lucrari-programate-{date_str}'

def check_sector(sector_cautat):
    try:
        url = get_tomorrow_url()
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        text_clean = soup.get_text(separator='\n')

        pattern = rf'{re.escape(sector_cautat)}:\s*(.*?)\s*(?:Chişinău, sectorul|\Z)'
        match = re.search(pattern, text_clean, re.DOTALL)

        if match:
            extracted_text = match.group(1).strip()
            return f'{sector_cautat}:\n{extracted_text}'
        else:
            return f'{sector_cautat} nu a fost găsit.'
    except requests.RequestException as e:
        return f'Eroare la request: {e}'

async def check_sector_async(sector_cautat):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(check_sector, sector_cautat))

# ✅ Trimite periodic mesaje doar către utilizatori care au interacționat
async def send_notifications(app):
    print(f"[{datetime.now()}] 📤 Trimit notificări programate...")

    for user_id, sector in user_sectors.items():
        msg = await check_sector_async(sector or "Chişinău, sectorul Botanica")
        try:
            await app.bot.send_message(chat_id=user_id, text=msg)
        except Exception as e:
            print(f"[Eroare] Nu pot trimite mesaj către user {user_id}: {e}")

# ✅ /start – Înregistrează utilizatorul și oferă opțiunea de alegere sector
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = {
        "id": user_id,
        "first_name": update.effective_user.first_name
    }
    all_users[user_id] = user_data
    if user_id not in user_sectors:
        user_sectors[user_id] = "Chişinău, sectorul Botanica"  # default

    keyboard = [[InlineKeyboardButton(sector, callback_data=f'sector|{sector}')] for sector in SECTOARE]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        "👋 Salut și bine ai venit la *Premier Energy Bot!*\n\n"
        "🔌 Aici poți vedea lucrările planificate de întrerupere a curentului pentru sectorul tău din Chișinău.\n\n"
        "📍 Alege sectorul tău din listă pentru a primi notificări automate.\n"
        "⏱️ Verificările se fac automat la fiecare 2 minute.\n\n"
        "👇 Selectează un sector din listă:"
    )

    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode="Markdown")

# ✅ Handler pentru butoane
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data.startswith("sector|"):
        sector = query.data.split("|", 1)[1]
        user_sectors[user_id] = sector
        context.user_data["sector"] = sector
        await query.message.reply_text(f"✅ Sector selectat: {sector}\nPoți folosi comanda /verifica pentru a vedea lucrările.")

    elif query.data == "check_now":
        sector = user_sectors.get(user_id, "Chişinău, sectorul Botanica")
        msg = await check_sector_async(sector)
        await query.message.reply_text(msg)

# ✅ /verifica – verifică pentru sectorul curent al utilizatorului
async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sector = user_sectors.get(user_id, "Chişinău, sectorul Botanica")
    msg = await check_sector_async(sector)
    await update.message.reply_text(msg)

async def check_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != CHAT_ID:
        await update.message.reply_text("⛔ Nu ai permisiunea să folosești această comandă.")
        return

    if not all_users:
        await update.message.reply_text("📭 Niciun utilizator înregistrat încă.")
        return

    user_list = ""
    for uid, data in all_users.items():
        name = data.get("first_name", "") + " " + (data.get("last_name") or "")
        username = f"@{data['username']}" if data.get("username") else "—"
        user_list += f"👤 {name.strip()} | {username} | ID: `{uid}`\n"

    await update.message.reply_text(f"📋 Utilizatori înregistrați:\n\n{user_list}", parse_mode="Markdown")


async def on_startup(app):
    print("🚀 Startup: Configurez programarea notificărilor.")
    scheduler = AsyncIOScheduler()

    # Trimitere la ora 10:00 dimineața
    scheduler.add_job(send_notifications, CronTrigger(hour=10, minute=0), args=[app])

    # Trimitere la ora 20:00 seara
    scheduler.add_job(send_notifications, CronTrigger(hour=20, minute=0), args=[app])
    scheduler.add_job(send_notifications, CronTrigger(hour=23, minute=59), args=[app])

    scheduler.start()
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verifica", verifica))
    app.add_handler(CommandHandler("check_users", check_users))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.post_init = on_startup  # startup-ul periodic

    print("Botul rulează public...")
    app.run_polling()
