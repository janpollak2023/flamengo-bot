import os, threading
from keep_alive import run as keep_alive_run
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ahoj, tady Kiki Tipy. Jedu! ✅")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

def start_keep_alive():
    t = threading.Thread(target=keep_alive_run, daemon=True)
    t.start()

def main():
    if not TOKEN:
        raise RuntimeError("Chybí env proměnná TELEGRAM_TOKEN")
    start_keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
