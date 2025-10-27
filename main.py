import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === Flask App ===
app = Flask(__name__)

# === Env proměnné ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
SECRET_PATH = os.getenv("SECRET_PATH")
PUBLIC_URL = os.getenv("PUBLIC_URL")

# === Telegram Application ===
application = Application.builder().token(TOKEN).build()


# === Příkazy ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot běží! Flamengo systém aktivní.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 Status: ONLINE\nRender server LIVE.")

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Generuji Flamengo tipy... chvíli strpení...")

async def tip24(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Tipy pro 24h budou připravené později...")

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧩 Debug aktivní – vše funkční.")


# === Registrace příkazů ===
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))
application.add_handler(CommandHandler("tip", tip))
application.add_handler(CommandHandler("tip24", tip24))
application.add_handler(CommandHandler("debug", debug))


# === Webhook inicializace ===
async def _startup(public_url: str, secret_path: str):
    """Inicializace aplikace a registrace webhooku"""
    await application.initialize()
    await application.start()
    url = f"{public_url.rstrip('/')}/{secret_path}"
    await application.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES)
    print(f"✅ Webhook registered at: {url}")
    return url


# === Flask route pro Telegram webhook ===
@app.post(f"/{SECRET_PATH}")
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
    except Exception as e:
        print("⚠️ Webhook error:", e)
        return "ERR", 500
    return "OK", 200


# === Health Check pro Render ===
@app.route("/healthz")
def healthz():
    return "OK", 200


# === Hlavní spouštěcí blok ===
if __name__ == "__main__":
    mode = os.getenv("MODE", "webhook").lower()

    if mode == "polling":
        print("🔁 Running in polling mode...")
        application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    else:
        print("🌐 Starting Flask webhook mode...")
        assert TOKEN and PUBLIC_URL and SECRET_PATH, "Missing required env vars!"
        asyncio.run(_startup(PUBLIC_URL, SECRET_PATH))
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
