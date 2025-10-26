import os, logging, threading, asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(name)s: %(message)s")
log = logging.getLogger("kiki-bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://flamengo-bot.onrender.com")
SECRET_PATH = os.getenv("SECRET_PATH", "webhook")
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET")

if not TELEGRAM_TOKEN or not PUBLIC_URL:
    log.error("Chybí TELEGRAM_TOKEN nebo PUBLIC_URL v env!")

app = Flask(__name__)
application: Application = Application.builder().token(TELEGRAM_TOKEN).build()

async def cmd_start(update: Update, _):
    await update.message.reply_text("Ahoj, jsem online ✅")
async def cmd_status(update: Update, _):
    await update.message.reply_text("alive ✅")

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))

loop = asyncio.new_event_loop()
def _run_loop():
    asyncio.set_event_loop(loop); loop.run_forever()
threading.Thread(target=_run_loop, daemon=True).start()

async def _boot():
    try:
        await application.initialize()
        url = f"{PUBLIC_URL.rstrip('/')}/{SECRET_PATH}"
        await application.bot.set_webhook(
            url=url,
            secret_token=TELEGRAM_SECRET if TELEGRAM_SECRET else None,
            drop_pending_updates=True
        )
        await application.start()
        log.info(f"Webhook set OK → {url}")
    except Exception as e:
        log.exception(f"Webhook/start error: {e}")

asyncio.run_coroutine_threadsafe(_boot(), loop)

@app.get("/healthz")
def healthz(): return "ok", 200

@app.post(f"/{SECRET_PATH}")
def telegram_webhook():
    if TELEGRAM_SECRET:
        if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_SECRET:
            return "forbidden", 403
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    except Exception as e:
        log.exception(f"process_update error: {e}")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
