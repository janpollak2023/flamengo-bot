# main.py  — Flask 3 + python-telegram-bot 21.6 (webhook přes Flask)
import os
import asyncio
from flask import Flask, request, jsonify, abort
from telegram import Update
from telegram.ext import Application, CommandHandler

# ====== ENV ======
PUBLIC_URL   = os.getenv("PUBLIC_URL", "").rstrip("/")
SECRET_PATH  = os.getenv("SECRET_PATH", "webhook")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not PUBLIC_URL or not TELEGRAM_TOKEN:
    raise RuntimeError("Chybí PUBLIC_URL nebo TELEGRAM_TOKEN v env.")

# ====== Flask ======
app = Flask(__name__)

# ====== PTB Application ======
application = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Handlery (jednoduché) ---
async def start_cmd(update, context):
    await update.message.reply_text("Ahoj, jsem Kiki bot. Použij /tip nebo /status.")

async def status_cmd(update, context):
    await update.message.reply_text("✅ Bot běží (webhook).")

# sem můžeš doplnit své funkce pro /tip, /tip24 atd.
application.add_handler(CommandHandler("start", start_cmd))
application.add_handler(CommandHandler("status", status_cmd))

# ====== Inicializace PTB + webhook při startu procesu ======
async def _startup():
    # inici PTB (nepouštíme polling, jen příjem webhooků)
    await application.initialize()
    await application.start()

    # nastav webhook (idempotentní – klidně opakovaně)
    url = f"{PUBLIC_URL}/{SECRET_PATH}"
    try:
        await application.bot.set_webhook(url=url, allowed_updates=["message"])
    except Exception as e:
        # nechceme spadnout při deployi kvůli dočasné chybě
        print(f"[WARN] set_webhook failed: {e}")

# spustíme hned při importu modulu (Flask 3 je WSGI – nevadí)
asyncio.get_event_loop().run_until_complete(_startup())

# ====== Routes ======
@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/status")
def status_page():
    return jsonify({"status": "live", "webhook": f"{PUBLIC_URL}/{SECRET_PATH}"}), 200

# Telegram → náš webhook endpoint
@app.post(f"/{SECRET_PATH}")
async def telegram_webhook():
    if request.headers.get("content-type", "").startswith("application/json"):
        data = request.get_json(force=True, silent=True)
        if not data:
            abort(400)
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return "ok", 200
    abort(415)

# volitelné – ruční přenastavení webhooku (pro debug)
@app.get("/setup")
async def setup_webhook():
    url = f"{PUBLIC_URL}/{SECRET_PATH}"
    try:
        asyncio.get_event_loop().run_until_complete(
            application.bot.set_webhook(url=url, allowed_updates=["message"])
        )
        return jsonify({"set_webhook": url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
