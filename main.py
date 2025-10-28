# main.py — MINIMAL WEBHOOK BOT (python-telegram-bot 21.6)
# Start Command na Renderu:  python main.py
# Build Command:             pip install -r requirements.txt

import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ---- ENV ----
TOKEN        = os.getenv("TELEGRAM_TOKEN", "").strip()
PUBLIC_URL   = os.getenv("PUBLIC_URL", "").rstrip("/")  # např. https://flamengo-bot.onrender.com
SECRET_PATH  = os.getenv("SECRET_PATH", "/webhook").strip()  # např. /tvuj_tajny_hook
if not SECRET_PATH.startswith("/"):
    SECRET_PATH = "/" + SECRET_PATH
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET", "").strip()
PORT         = int(os.getenv("PORT", "10000"))

# ---- HANDLERY ----
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ahoj Honzo! 🟢 Jedu.\n/status = kontrola\n/tip = připraveno.",
        parse_mode=ParseMode.HTML,
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tip modul připraven – napojíme gól do poločasu.")

# diagnostické echo, ať hned vidíš reakci
async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(f"Echo: {update.message.text[:120]}")

def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip",    tip_cmd))
    app.add_handler(MessageHandler(filters.ALL, echo_all))
    return app

def main():
    app = build_app()
    # PTB spustí vlastní HTTP server a nastaví webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=SECRET_PATH.lstrip("/"),
        webhook_url=f"{PUBLIC_URL}{SECRET_PATH}",
        secret_token=SECRET_TOKEN if SECRET_TOKEN else None,
        allowed_updates=["message", "edited_message", "callback_query"],
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
