import os, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PUBLIC_URL = os.environ["PUBLIC_URL"]
PORT = int(os.environ.get("PORT", "10000"))

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ahoj, tady Kiki Tipy. Jedu! ✅")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot běží (webhook)\nTZ: Europe/Prague")

async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 Bezpečnostní tiket\n• Hokej — 2. třetina góly: Over 1.5\n  Důvěra: 86%\n\n"
        "⚠️ Risk tiket\n• Fotbal — gól do poločasu: ANO\n  Důvěra: 72%"
    )

async def run():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("tip", cmd_tip))

    webhook_path = f"webhook/{TOKEN}"
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(url=f"{PUBLIC_URL}/{webhook_path}")

    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
    )

if __name__ == "__main__":
    asyncio.run(run())
