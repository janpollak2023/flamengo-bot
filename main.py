# main.py — Telegram bot KikiTipy (Render 24/7 + fallback polling, PTB 21.x)
import os, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ====== ENV ======
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PUBLIC_URL = (
    os.environ.get("PUBLIC_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or ("https://" + os.environ.get("RENDER_EXTERNAL_HOSTNAME", ""))
)
PORT = int(os.environ.get("PORT", "10000"))

# ====== COMMANDS ======
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ahoj, tady Kiki Tipy. Jedu! ✅")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot běží\nRežim: webhook/polling (auto)\nTZ: Europe/Prague")

async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 Bezpečnostní tiket\n• Hokej — 2. třetina góly: Over 1.5\n  Důvěra: 86%\n\n"
        "⚠️ Risk tiket\n• Fotbal — gól do poločasu: ANO\n  Důvěra: 72%"
    )

# ====== BOOTSTRAP ======
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("tip", cmd_tip))

    webhook_path = f"webhook/{TOKEN}"

    # Fallback: když PUBLIC_URL není známá, jedeme POLLING
    if not PUBLIC_URL or PUBLIC_URL == "https://":
        print("⚠️ PUBLIC_URL nenalezen – spouštím POLLING mód.")
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.initialize()
        await app.start()
        await app.updater.start_polling()   # PTB 21.x – stále k dispozici
        await app.updater.idle()
        return

    # WEBHOOK mód (Render)
    print(f"✅ Spouštím WEBHOOK: {PUBLIC_URL}/{webhook_path}")
    await app.bot.delete_webhook(drop_pending_updates=True)
    await app.bot.set_webhook(url=f"{PUBLIC_URL}/{webhook_path}")
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
    )

if __name__ == "__main__":
    asyncio.run(main())
