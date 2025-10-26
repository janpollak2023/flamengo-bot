# main.py
import os
import json
import time
import hmac
import hashlib
import logging
import threading
import asyncio
from datetime import datetime

from flask import Flask, request, jsonify, abort

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --------------------
# Konfigurace & logging
# --------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("kiki-bot")

TOKEN = os.getenv("TELEGRAM_TOKEN")  # povinné
PUBLIC_URL = os.getenv("PUBLIC_URL")  # povinné (např. https://flamengo-bot.onrender.com)
TELEGRAM_SECRET = os.getenv("TELEGRAM_SECRET", "")  # doporučeno
SECRET_PATH = os.getenv("SECRET_PATH", "webhook")  # např. náhodný řetězec

if not TOKEN or not PUBLIC_URL:
    log.error("Chybí TELEGRAM_TOKEN nebo PUBLIC_URL v env!")
    # Nezastavujeme proces, aby Render ukázal logy/healthz, ale bot nebude funkční.

# --------------------
# Flask app
# --------------------
app = Flask(__name__)

# --------------------
# Async event loop na pozadí pro PTB
# --------------------
loop = asyncio.new_event_loop()
thread = threading.Thread(target=loop.run_forever, name="kiki-loop", daemon=True)
thread.start()

# --------------------
# Telegram Application (PTB v21+)
# --------------------
tg_app: Application = Application.builder().token(TOKEN).build() if TOKEN else None


# --------------------
# Command handlers
# --------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        "Ahoj, tady Kiki 🤖\nJsem připravená. Zkus /status, /tip, /tip24 nebo /debug."
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wb = await context.bot.get_webhook_info()
    parts = [
        f"⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"🌐 PUBLIC_URL: {PUBLIC_URL}",
        f"🛣  SECRET_PATH: /{SECRET_PATH}",
        f"🔗 Webhook URL (na boku Telegramu): {wb.url or '—'}",
        f"📬 Pending updates: {wb.pending_update_count}",
        f"🔒 Has custom cert: {wb.has_custom_certificate}",
        f"🚦 Last error date: {wb.last_error_date or '—'}",
        f"⚠️ Last error msg: {wb.last_error_message or '—'}",
        "✅ Aplikace běží.",
    ]
    await update.effective_chat.send_message("\n".join(parts))


async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Placeholder – sem pak přidáme napojení na tvoje analyzéry/endpointy
    await update.effective_chat.send_message(
        "🎯 /tip – demo odpověď.\nZatím bez napojení na Tipsport scraping.\n"
        "Pošli mi specifikaci (sport, soutěž, trh) nebo použij /tip24.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_tip24(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        "🗓 /tip24 – demo: vrátím prázdný seznam. "
        "Až napojíme zdroje, pošlu 2× Bezpečí + 2× Risk dle Flamengo.",
    )


async def cmd_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.effective_message.text or ""
    payload = text.split(maxsplit=1)[1] if " " in text else "(bez payloadu)"
    await update.effective_chat.send_message(
        f"🔍 DEBUG OK\npayload: <code>{payload}</code>", parse_mode=ParseMode.HTML
    )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # fallback na volný text
    await update.effective_chat.send_message(
        "👋 Zkus příkazy: /start /status /tip /tip24 /debug"
    )


# --------------------
# Registrace handlerů
# --------------------
if tg_app:
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("status", cmd_status))
    tg_app.add_handler(CommandHandler("tip", cmd_tip))
    tg_app.add_handler(CommandHandler("tip24", cmd_tip24))
    tg_app.add_handler(CommandHandler("debug", cmd_debug))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))


# --------------------
# Webhook setup
# --------------------
async def _startup():
    if not tg_app:
        return
    await tg_app.initialize()
    # Spustí interní job queue/dispatcher, ale NESPÍNÁ vlastní server
    await tg_app.start()
    # Nastaví webhook u Telegramu na náš Flask endpoint
    url = f"{PUBLIC_URL.rstrip('/')}/{SECRET_PATH}"
    try:
        await tg_app.bot.set_webhook(
            url=url,
            secret_token=TELEGRAM_SECRET if TELEGRAM_SECRET else None,
            drop_pending_updates=True,
        )
        log.info(f"Webhook nastaven na: {url}")
    except Exception:
        log.exception("Nepodařilo se nastavit webhook.")


# plán startu PTB v běžícím loopu
if tg_app:
    asyncio.run_coroutine_threadsafe(_startup(), loop)


# --------------------
# Bezpečnostní pomocné funkce
# --------------------
def _check_secret_header(req) -> bool:
    """Volitelná validace Telegram headeru (X-Telegram-Bot-Api-Secret-Token)."""
    if not TELEGRAM_SECRET:
        return True  # když není nastaveno, nevalidujeme
    return req.headers.get("X-Telegram-Bot-Api-Secret-Token") == TELEGRAM_SECRET


# --------------------
# Flask routes
# --------------------
@app.get("/")
def root():
    return jsonify(
        name="Kiki tipy bot",
        ok=True,
        time_utc=datetime.utcnow().isoformat() + "Z",
        webhook=f"/{SECRET_PATH}",
    )


@app.get("/healthz")
def healthz():
    status = {
        "ok": True,
        "time_utc": datetime.utcnow().isoformat() + "Z",
        "has_token": bool(TOKEN),
        "public_url": PUBLIC_URL,
        "secret_path": f"/{SECRET_PATH}",
        "thread_alive": thread.is_alive(),
    }
    return jsonify(status), 200


@app.post(f"/{SECRET_PATH}")
def webhook():
    if not tg_app:
        log.error("Webhook hit, ale tg_app není inicializována.")
        return ("bot not ready", 503)

    if not _check_secret_header(request):
        log.warning("Webhook: špatný/nepřítomný secret header.")
        abort(401)

    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        log.exception("Webhook: nevalidní JSON.")
        abort(400)

    try:
        update = Update.de_json(data, tg_app.bot)
    except Exception:
        log.exception("Webhook: Update.de_json selhal.")
        abort(400)

    # předat update do PTB v našem event loopu
    fut = asyncio.run_coroutine_threadsafe(tg_app.process_update(update), loop)
    try:
        # Neblokujeme dlouho – jen ověříme, že se task zařadil
        fut.result(timeout=0.25)
    except Exception:
        # Je to ok – PTB si to zpracuje asynchronně; nechceme 5xx kvůli timeoutu
        pass

    return ("ok", 200)


# --------------------
# Lokální vývoj (python main.py)
# --------------------
if __name__ == "__main__":
    # Pro lokální test bez gunicornu
    port = int(os.getenv("PORT", "8000"))
    log.info(f"Start Flask dev serveru na :{port}")
    app.run(host="0.0.0.0", port=port)
