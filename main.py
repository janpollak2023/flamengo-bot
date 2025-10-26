import os, re, logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(name)s: %(message)s")
log = logging.getLogger("bot")

# TOKEN – očista neviditelných znaků
RAW = os.getenv("TELEGRAM_TOKEN", "")
TOKEN = re.sub(r"[^A-Za-z0-9:_-]", "", RAW)
if TOKEN != RAW:
    log.warning(f"Token cleaned: {len(RAW)} -> {len(TOKEN)}")
log.info(f"FINGERPRINT: ***{TOKEN[-6:]}")

async def start_cmd(u: Update, _):  await u.message.reply_text("Ahoj, jsem online ✅")
async def status_cmd(u: Update, _): await u.message.reply_text("alive ✅")
async def echo(u: Update, _):
    if u.message and u.message.text:
        await u.message.reply_text("echo: " + u.message.text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    log.info("RUNNING: polling mode (no webhook)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
