# main.py — MINIMAL PTB WEBHOOK (bez Flasku, ověřeno s python-telegram-bot==21.6)

import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN        = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL   = os.getenv("PUBLIC_URL", "").rstrip("/")
SECRET_PATH  = os.getenv("SECRET_PATH", "/webhook")
if not SECRET_PATH.startswith("/"):
    SECRET_PATH = "/" + SECRET_PATH
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET", "")
PORT         = int(os.getenv("PORT", "10000"))

# --- Handlery ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ahoj Honzíku! 🟢 Jedu.\n/status = kontrola\n/tip = připraveno.",
        parse_mode=ParseMode.HTML
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tip modul připraven – napojíme gól do poločasu.")

async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(f"Echo: {update.message.text[:120]}")

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip",    tip_cmd))
    app.add_handler(MessageHandler(filters.ALL, echo_all))

    # PTB spustí vlastní web server a sám nastaví webhook
    webhook_url = f"{PUBLIC_URL}{SECRET_PATH}"
    await app.initialize()
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await app.bot.set_webhook(
        url=webhook_url,
        secret_token=SECRET_TOKEN if SECRET_TOKEN else None,
        allowed_updates=["message","edited_message","callback_query"]
    )
    await app.start()
    # Vestavěný HTTP server PTB
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=SECRET_PATH.lstrip("/"),
        secret_token=SECRET_TOKEN if SECRET_TOKEN else None,
    )
    # běž navždy
    await app.updater.wait_until_closed()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
