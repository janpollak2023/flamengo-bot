import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
SECRET_PATH = os.getenv("SECRET_PATH")
PUBLIC_URL = os.getenv("PUBLIC_URL")

if not TOKEN or not SECRET_PATH or not PUBLIC_URL:
    raise RuntimeError("Missing env vars: TELEGRAM_TOKEN / SECRET_PATH / PUBLIC_URL")

application = Application.builder().token(TOKEN).build()

# ----- Commands -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot běží! Flamengo systém aktivní.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🟢 Status: ONLINE (Render live)")

async def tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Generuji Flamengo tipy…")

async def tip24(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Tipy pro 24h – WIP.")

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧩 Debug OK.")

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("status", status))
application.add_handler(CommandHandler("tip", tip))
application.add_handler(CommandHandler("tip24", tip24))
application.add_handler(CommandHandler("debug", debug))

# ----- Webhook init -----
async def _startup(public_url: str, secret_path: str):
    await application.initialize()
    await application.start()
    url = f"{public_url.rstrip('/')}/{secret_path}"
    await application.bot.set_webhook(url=url, allowed_updates=Update.ALL_TYPES)
    print(f"✅ Webhook registered at: {url}")

# Gunicorn neprovede __main__, proto registraci spustíme při prvním requestu (např. /healthz)
_started = False
@app.before_first_request
def _ensure_webhook():
    global _started
    if _started:
        return
    _started = True
    try:
        asyncio.run(_startup(PUBLIC_URL, SECRET_PATH))
    except Exception as e:
        print("⚠️ Webhook init failed:", e)

# ----- Telegram webhook endpoint -----
@app.post(f"/{SECRET_PATH}")
def telegram_webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
        return "OK", 200
    except Exception as e:
        print("⚠️ Webhook error:", e)
        return "ERR", 500

# ----- Health check -----
@app.get("/healthz")
def healthz():
    return "OK", 200

# Lokální běh (ne Render)
if __name__ == "__main__":
    asyncio.run(_startup(PUBLIC_URL, SECRET_PATH))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
