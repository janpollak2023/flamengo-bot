# main.py
import os
import threading
import asyncio
from flask import Flask, request

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler

# === ENV ===
TOKEN         = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL    = os.getenv("PUBLIC_URL", "").rstrip("/")
SECRET_PATH   = os.getenv("SECRET_PATH", "/webhook")  # např. "/tvuj_tajny_hook"
SECRET_TOKEN  = os.getenv("TELEGRAM_SECRET", "")      # libovolný dlouhý string

# === Telegram Application (PTB 21.6) ===
application: Application = Application.builder().token(TOKEN).build()

async def cmd_start(update: Update, _):
    await update.message.reply_text(
        "Ahoj Honzíku! Jedu.\n/status = kontrola\n/tip = připraveno na tipy.",
        parse_mode=ParseMode.HTML
    )

async def cmd_status(update: Update, _):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def cmd_tip(update: Update, _):
    # TODO: tady později napojíme scraper a Flamengo filtr
    await update.message.reply_text("Tip modul připraven – napojíme scraper na Tipsport.")

application.add_handler(CommandHandler("start",  cmd_start))
application.add_handler(CommandHandler("status", cmd_status))
application.add_handler(CommandHandler("tip",    cmd_tip))

# === Flask app ===
app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return "OK", 200

# Registrujeme PŘESNĚ tu cestu, kterou posílá Telegram (např. /tvuj_tajny_hook)
@app.post(SECRET_PATH)
def telegram_webhook():
    # Ochrana přes secret token v hlavičce (musí se shodovat s TELEGRAM_SECRET)
    if SECRET_TOKEN and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET_TOKEN:
        return "forbidden", 403
    data = request.get_json(silent=True, force=True)
    if not data:
        return "no json", 400
    update = Update.de_json(data, application.bot)
    # předáme update do PTB fronty
    application.update_queue.put_nowait(update)
    return "ok", 200

# === Spuštění PTB v pozadí + nastavení webhooku ===
_started = False

def _run_ptb_loop():
    """
    Spustí PTB v samostatném event loopu na pozadí
    a zaregistruje webhook na PUBLIC_URL + SECRET_PATH.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _boot():
        # bezpečné pře-nastavení webhooku
        await application.initialize()
        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass
        if PUBLIC_URL and SECRET_PATH:
            url = f"{PUBLIC_URL}{SECRET_PATH}"
            await application.bot.set_webhook(
                url=url,
                secret_token=SECRET_TOKEN if SECRET_TOKEN else None,
                allowed_updates=["message", "edited_message", "callback_query"]
            )
        await application.start()

    loop.run_until_complete(_boot())
    # běžíme navždy – PTB zpracovává updaty z fronty
    loop.run_forever()

def _ensure_started():
    global _started
    if not _started:
        # Spouštíme na 1 vlákně – v Renderu používej -w 1
        t = threading.Thread(target=_run_ptb_loop, name="ptb-thread", daemon=True)
        t.start()
        _started = True

# Spustíme PTB hned při importu (když gunicorn natahuje app)
_ensure_started()

# ---- Gunicorn entrypoint: main:app ----
# Start command v Renderu:
# gunicorn -w 1 -k gthread -b 0.0.0.0:$PORT main:app
