# main.py – Kiki Tipy bot (Render webhook + fallback polling) • PTB 21.x
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from tip_engine import suggest_today, suggest_full, debug_report  # nové funkce

# --- ENV ---
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PUBLIC_URL = (
    os.environ.get("PUBLIC_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or ("https://" + os.environ.get("RENDER_EXTERNAL_HOSTNAME", ""))
)
PORT = int(os.environ.get("PORT", "10000"))

# --- Commands ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ahoj, tady Kiki Tipy. Jedu! ✅")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot běží\nRežim: webhook/polling (auto)\nTZ: Europe/Prague")

async def cmd_tip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = suggest_today()
    await update.message.reply_text(text)

# nový příkaz – /tip24 (celodenní hledání)
async def cmd_tip24(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = suggest_full()
    await update.message.reply_text(text)

# nový příkaz – /debug (report kolik zápasů bylo nalezeno a prošlo filtry)
async def cmd_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = debug_report()
    await update.message.reply_text(text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("tip", cmd_tip))
    app.add_handler(CommandHandler("tip24", cmd_tip24))
    app.add_handler(CommandHandler("debug", cmd_debug))

    path = f"/webhook/{TOKEN}"

    if not PUBLIC_URL or PUBLIC_URL == "https://":
        print("⚙️ PUBLIC_URL nenalezen — spouštím POLLING mód.")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        return

    print(f"⚙️ Spouštím WEBHOOK: {PUBLIC_URL}{path}")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=path,
        webhook_url=f"{PUBLIC_URL}{path}",
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

if __name__ == "__main__":
    main()
