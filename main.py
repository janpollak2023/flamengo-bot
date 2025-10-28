# main.py (verze s diagnostikou)
import os, threading, asyncio, logging
from flask import Flask, request
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("flamengo-bot")

# --- ENV ---
TOKEN        = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL   = os.getenv("PUBLIC_URL", "").rstrip("/")
SECRET_PATH  = os.getenv("SECRET_PATH", "/webhook")
if not SECRET_PATH.startswith("/"):
    SECRET_PATH = "/" + SECRET_PATH
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET", "")

# --- TELEGRAM APP ---
application: Application = Application.builder().token(TOKEN).build()

async def cmd_start(update: Update, _):
    await update.message.reply_text("Ahoj, jedu. /status = kontrola, /tip = připraveno.")

async def cmd_status(update: Update, _):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def cmd_tip(update: Update, _):
    await update.message.reply_text("Tip modul připraven – napojíme scraper.")

# DIAGNOSTICKÝ ECHO, ať vidíme reakci na jakoukoliv zprávu
async def echo_all(update: Update, _):
    if update.message and update.message.text:
        await update.message.reply_text(f"Echo: {update.message.text[:100]}")

application.add_handler(CommandHandler("start",  cmd_start))
application.add_handler(CommandHandler("status", cmd_status))
application.add_handler(CommandHandler("tip",    cmd_tip))
application.add_handler(MessageHandler(filters.ALL, echo_all))

# --- FLASK ---
app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return "OK", 200

@app.post(SECRET_PATH)
def telegram_webhook():
    log.info("WEBHOOK HIT %s headers=%s", SECRET_PATH, dict(request.headers))
    if SECRET_TOKEN and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET_TOKEN:
        log.warning("WEBHOOK 403 – secret token mismatch")
        return "forbidden", 403

    data = request.get_json(silent=True, force=True)
    if not data:
        log.warning("WEBHOOK 400 – no json")
        return "no json", 400

    try:
        update = Update.de_json(data, application.bot)

        # ⬇️ KLÍČOVÁ ZMĚNA: zpracujeme update okamžitě
        # (bez fronty), aby při restartech/latenci nic "nepropadlo".
        application.create_task(application.process_update(update))
        log.info("WEBHOOK OK – update processed (id=%s)", update.update_id)
        return "ok", 200
from telegram.error import TelegramError

async def on_error(update, context):
    log.exception("HANDLER ERROR: %s | cause=%s", context.error, getattr(context, "error", None))

application.add_error_handler(on_error)
    except Exception as e:
        log.exception("WEBHOOK 500 – failed to process update: %s", e)
        return "error", 500

# --- PTB START NA POZADÍ ---
_started = False
def _run_ptb_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def boot():
        log.info("PTB initialize()…")
        await application.initialize()
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        if PUBLIC_URL and SECRET_PATH:
            url = f"{PUBLIC_URL}{SECRET_PATH}"
            log.info("Setting webhook to %s", url)
            await application.bot.set_webhook(
                url=url,
                secret_token=SECRET_TOKEN if SECRET_TOKEN else None,
                allowed_updates=["message","edited_message","callback_query"]
            )
        log.info("PTB start()…")
        await application.start()
        log.info("PTB started.")

    loop.run_until_complete(boot())
    loop.run_forever()

def _ensure_started():
    global _started
    if not _started:
        t = threading.Thread(target=_run_ptb_loop, name="ptb-thread", daemon=True)
        t.start()
        _started = True
        log.info("PTB thread spawned.")

_ensure_started()
# Gunicorn entrypoint: main:app
# Start command: gunicorn -w 1 -k gthread -b 0.0.0.0:$PORT main:app
