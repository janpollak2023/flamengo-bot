# main.py — Flask 3 + PTB v21, bez webhooku (long-polling)
import os
import threading
import logging
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ----- Logging -----
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("flamengo-bot")

# ===== Telegram Application =====
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_TOKEN env var")

application = Application.builder().token(TOKEN).build()

# --- Handlery ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ahoj! Jsem Flamengo bot.\n"
        "Příkazy: /status, /tip"
    )

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("✅ Žiju. Nasazený na Renderu, režim long-polling.")

# Tipy – voláme tvůj engine
def _suggest_sync() -> str:
    try:
        from tip_engine import suggest_today  # tvoje funkce
        return suggest_today()
    except Exception as e:
        log.exception("tip_engine error")
        return f"❌ Chyba v tip_engine: {e}"

async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # PTB handler je async; výpočet provedeme v thread poolu
    loop = context.application.bot.loop
    text = await loop.run_in_executor(None, _suggest_sync)
    await update.message.reply_text(text or "Dnes nic silného nenašlo.")

application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))
application.add_handler(CommandHandler("tip", cmd_tip))

# ===== Flask app (sync) =====
app = Flask(__name__)
app.config["BOT_THREAD"] = None

@app.get("/healthz")
def healthz():
    return jsonify(ok=True)

# Volitelný rychlý náhled (není webhook)
@app.get("/suggest")
def suggest_http():
    return _suggest_sync(), 200, {"Content-Type": "text/plain; charset=utf-8"}

# Spuštění PTB v samostatném vlákně (jen jednou na worker)
def _start_bot_once():
    if app.config["BOT_THREAD"] is None:
        t = threading.Thread(
            target=lambda: application.run_polling(
                close_loop=False,
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            ),
            daemon=True,
            name="ptb-polling",
        )
        t.start()
        app.config["BOT_THREAD"] = t
        log.info("PTB polling thread started.")

# Při importu modulu ihned nastartuj bota (gunicorn worker)
_start_bot_once()

# Gunicorn entrypoint: "main:app"
