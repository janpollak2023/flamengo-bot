import os, re, logging
from datetime import datetime, timedelta, timezone
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

# --- Pomocné formátování ---
def fmt_tip(dt, liga, zapas, trh, pick, kurz, conf):
    t = dt.strftime("%d.%m. %H:%M")
    return (
        f"🕒 {t}  •  {liga}\n"
        f"⚽ {zapas}\n"
        f"🎯 {trh}: *{pick}*  @ {kurz}\n"
        f"💡 Důvěra: *{conf}%*\n"
        f"— — —"
    )

# --- Mock data (ukázkové) ---
def mock_today():
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    return [
        fmt_tip(now.replace(hour=18, minute=30), "CZ1", "Plzeň vs Ostrava", "Góly 2–6", "Over 2.0", "1.62", 90),
        fmt_tip(now.replace(hour=20, minute=00), "ENG Champ", "Leeds vs Hull", "HT góly", "HT Over 0.5", "1.55", 89),
        fmt_tip(now.replace(hour=21, minute=00), "ITA Serie B", "Parma vs Pisa", "Rohy hostů", "Hosté > 2.5", "1.80", 86),
    ]

def mock_24h():
    base = datetime.now(timezone.utc) + timedelta(hours=2)
    tips = []
    seeds = [
        ("ESP LaLiga", "Betis vs Osasuna", "Góly 2–6", "Over 2.0", "1.70", 90, 4),
        ("GER 2.Bundesliga", "HSV vs Düsseldorf", "HT góly", "HT Over 0.5", "1.52", 88, 6),
        ("CZE Extraliga", "Sparta vs Třinec", "Třetiny góly", "1. tř. Over 0.5", "1.50", 87, 8),
        ("NHL", "Rangers vs Devils", "SOG hosté", "Hosté > 27.5", "1.85", 84, 10),
        ("UCL", "Inter vs Porto", "Rohy hostů", "Hosté > 2.5", "1.75", 82, 12),
        ("POL Ekstraklasa", "Legia vs Lech", "Karty hostů", "Hosté > 1.5", "1.90", 80, 14),
    ]
    for liga, zap, trh, pick, kurz, conf, addh in seeds:
        tips.append(fmt_tip(base + timedelta(hours=addh), liga, zap, trh, pick, kurz, conf))
    return tips

# --- Command handlers ---
async def start_cmd(u: Update, _):
    await u.message.reply_text(
        "Ahoj! 🟢 Jsem online.\n"
        "Zkus /tip, /tip24 nebo /live.\n"
        "Pro nápovědu /help."
    )

async def help_cmd(u: Update, _):
    await u.message.reply_text(
        "/tip – 1–3 tipy na dnes\n"
        "/tip24 – rozšířený výběr na 24 hodin\n"
        "/live – live monitoring (placeholder)\n"
        "/status – kontrola, že běžím"
    )

async def status_cmd(u: Update, _):
    await u.message.reply_text("alive ✅")

async def tip_cmd(u: Update, _):
    tips = mock_today()
    await u.message.reply_text("📊 *Dnešní výběr (beta)*", parse_mode="Markdown")
    for t in tips:
        await u.message.reply_text(t, parse_mode="Markdown")

async def tip24_cmd(u: Update, _):
    tips = mock_24h()
    await u.message.reply_text("⏱️ *Horizont 24h (beta)*", parse_mode="Markdown")
    for t in tips:
        await u.message.reply_text(t, parse_mode="Markdown")

async def live_cmd(u: Update, _):
    await u.message.reply_text("🟡 Live scanner běží (placeholder). Brzy přidáme feed + filtry 90%.")

async def echo(u: Update, _):
    if u.message and u.message.text and not u.message.text.startswith("/"):
        await u.message.reply_text("echo: " + u.message.text)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip", tip_cmd))
    app.add_handler(CommandHandler("tip24", tip24_cmd))
    app.add_handler(CommandHandler("live", live_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    log.info("RUNNING: polling mode (no webhook)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
