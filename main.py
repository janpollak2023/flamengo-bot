import os, re, logging, threading, asyncio, json
from flask import Flask, request
import urllib.request

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(name)s: %(message)s")
log = logging.getLogger("kiki-bot")

# === ENV ===
RAW_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL  = os.getenv("PUBLIC_URL", "").strip()
SECRET_PATH = os.getenv("SECRET_PATH", "webhook").strip()
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET", "").strip()

# 1) Očisti token od VŠECH neviditelných a nepovolených znaků (ponecháme jen A-Z a-z 0-9 : _ - )
CLEAN_TOKEN = re.sub(r"[^A-Za-z0-9:_-]", "", RAW_TOKEN)
if CLEAN_TOKEN != RAW_TOKEN:
    log.warning(f"Token měl neviditelné znaky – byl očištěn. Len={len(RAW_TOKEN)} -> {len(CLEAN_TOKEN)}")

# 2) Rychlý self-test přímo proti Telegramu (bez PTB), ať vidíme pravdu v logu
def telegram_get(path: str):
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{CLEAN_TOKEN}/{path}") as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}

probe = telegram_get("getMe")
log.info(f"GET /getMe -> {probe}")

if not PUBLIC_URL:
    log.error("Chybí PUBLIC_URL v env!")

app = Flask(__name__)

# === PTB app ===
application: Application = Application.builder().token(CLEAN_TOKEN).build()

async def cmd_start(update: Update, _):  await update.message.reply_text("Ahoj, jsem online ✅")
async def cmd_status(update: Update, _): await update.message.reply_text("alive ✅")
async def echo(update: Update, _):
    if update.message and update.message.text:
        await update.message.reply_text("echo: " + update.message.text)

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# === background loop ===
loop = asyncio.new_event_loop()
def run_loop(): asyncio.set_event_loop(loop); loop.run_forever()
threading.Thread(target=run_loop, daemon=True).start()

async def boot():
    try:
        await application.initialize()
        url = f"{PUBLIC_URL.rstrip('/')}/{SECRET_PATH}"
        await application.bot.set_webhook(url=url, secret_token=(TELEGRAM_SECRET or None), drop_pending_updates=True)
        await application.start()
        log.info(f"TOKEN FINGERPRINT: ***{CLEAN_TOKEN[-6:]}")
        log.info(f"Webhook set OK → {url}")
    except Exception as e:
        log.exception(f"Boot error: {e}")

asyncio.run_coroutine_threadsafe(boot(), loop)

@app.get("/healthz")
def healthz(): return "ok", 200

@app.post(f"/{SECRET_PATH}")
def webhook():
    if TELEGRAM_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != TELEGRAM_SECRET:
        return "forbidden", 403
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    except Exception as e:
        log.exception(f"process_update error: {e}")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
