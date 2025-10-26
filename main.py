import os, re, logging, asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(name)s: %(message)s")
log = logging.getLogger("bot")

# ===== TOKEN: očista neviditelných znaků (NBSP, \n, ZWSP atd.) =====
RAW = os.getenv("TELEGRAM_TOKEN", "")
TOKEN = re.sub(r"[^A-Za-z0-9:_-]", "", RAW)
if TOKEN != RAW:
    log.warning(f"Token cleaned: len {len(RAW)} -> {len(TOKEN)}")
log.info(f"FINGERPRINT: ***{TOKEN[-6:]}")

# ===== Handlery =====
async def start_cmd(u: Update, _):  await u.message.reply_text("Ahoj, jsem online ✅")
async def status_cmd(u: Update, _): await u.message.reply_text("alive ✅")
async def echo(u: Update, _):
    if u.message and u.message.text:
        await u.message.reply_text("echo: " + u.message.text)

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start_cmd))
app.add_handler(CommandHandler("status", status_cmd))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

async def main():
    # místo webhooku použijeme polling
    await app.initialize()
    await app.start()
    log.info("RUNNING: polling mode (no webhook)")
    await app.run_polling(close_loop=False)

if __name__ == "__main__":
    asyncio.run(main())
