import os
import logging
import threading
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# ---------- LOGGING ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s | %(name)s: %(message)s",
)
log = logging.getLogger("kiki-bot")

# ---------- ENV ----------
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")              # povinné
PUBLIC_URL      = os.getenv("PUBLIC_URL", "").strip()      # povinné (https://flamengo-bot.onrender.com)
SECRET_PATH     = os.getenv("SECRET_PATH", "webhook").strip()  # bez lomítka, např. "webhook"
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET", "").strip()     # volitelné

if not TELEGRAM_TOKEN or not PUBLIC_URL:
    log.error("Chybí TELEGRAM_TOKEN nebo PUBLIC_URL v env!")

# pro rychlou kontrolu, že se načetl opravdu správný token
log.info(f"TOKEN FINGERPRINT: ***{(TELEGRAM_TOKEN[-6:] if TELEGRAM_TOKEN else 'none')}")

# ---------- FLASK ----------
app = Flask(__name__)

# ---------- TELEGRAM (PTB v21) ----------
application: Application = Application.builder().token(TELEGRAM_TOKEN).build()

# /start
async def cmd_start(update: Update, _):
    await update.message.reply_text("Ahoj Honzo, jsem online ✅")

# /status
async def cmd_status(update: Update, _):
    await update.message.reply_text("alive ✅")

# DEBUG echo (pomáhá ověřit, že update opravdu teče přes webhook)
async def echo(update: Update, _):
    if update.message and update.message.text:
        await update.message.reply_text("echo: " + update.message.text)

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# ---------- ASYNC LOOP NA POZADÍ ----------
loop = asyncio.new_event_loop()
def _run_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_run_loop, daemon=True).start()

async def _boot():
    try:
        await application.initialize()
        webhook_url = f"{PUBLIC_URL.rstrip('/')}/{SECRET_PATH}"
        await application.bot.set_webhook(
            url=webhook_url,
            secret_token=(TELEGRAM_SECRET if TELEGRAM_SECRET else None),
            drop_pending_updates=True,
        )
        await application.start()
        log.info(f"Webhook set OK → {webhook_url}")
    except Exception as e:
        log.exception(f"Webhook/start error: {e}")

# spustit inicializaci bota na background loopu
asyncio.run_coroutine_threadsafe(_boot(), loop)

# ---------- ROUTES ----------
@app.get("/healthz")
def healthz():
    return "ok", 200

@app.post(f"/{SECRET_PATH}")
def telegram_webhook():
    # volitelné ověření tajného headeru
    if TELEGRAM_SECRET:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != TELEGRAM_SECRET:
            return "forbidden", 403
    try:
        data = request.get_json(force=True, silent=False)
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    except Exception as e:
        log.exception(f"process_update error: {e}")
    return "OK", 200

# pro lokální spuštění (Render používá gunicorn main:app)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
