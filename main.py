# main.py – Telegram bot Kiki Tipy 2
# ✅ Webhook + /start + /status + /tip (vyhledávání z picks.py)
# Start Command (Render): python main.py
# Build Command: pip install -r requirements.txt

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
from picks import find_first_half_goal_candidates   # importujeme náš modul na tipy

# ======================
#   ENVIRONMENT
# ======================
TOKEN        = os.getenv("TELEGRAM_TOKEN", "").strip()
PUBLIC_URL   = os.getenv("PUBLIC_URL", "").rstrip("/")  # např. https://flamengo-bot.onrender.com
SECRET_PATH  = os.getenv("SECRET_PATH", "/tvuj_tajny_hook").strip()
if not SECRET_PATH.startswith("/"):
    SECRET_PATH = "/" + SECRET_PATH
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET", "").strip()
PORT         = int(os.getenv("PORT", "10000"))

# ======================
#   HANDLERY
# ======================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ahoj Honzo! 🟢 Jedu.\n"
        "/status = kontrola\n"
        "/tip = vyhledávání zápasů (gól do poločasu)\n\n"
        "🔥 Bot je připravený na Flamengo strategii.",
        parse_mode=ParseMode.HTML,
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tips = find_first_half_goal_candidates(limit=3)

    if not tips:
        await update.message.reply_text("⚠️ Momentálně žádné zápasy nenalezeny.")
        return

    lines = []
    for i, t in enumerate(tips, 1):
        link = f"\n🔗 {t.url}" if t.url else ""
        kurz = f" @ {t.odds:.2f}" if t.odds else ""
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> ({t.league})\n"
            f"   Sázka: <b>{t.market}{kurz}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   Důvod: {t.reason}{link}"
        )

    msg = (
        "🔥 <b>Flamengo – gól do poločasu (TOP kandidáti)</b>\n"
        + "\n\n".join(lines)
        + "\n\n"
        "Pozn.: Pokud je zdroj dočasně blokovaný (Cloudflare), vidíš fallback návrhy. "
        "Při plném běhu se přidají přesné statistiky a kurzy."
    )
    await update.message.reply_html(msg)

# echo – jen testovací fallback
async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text(f"Echo: {update.message.text[:120]}")

# ======================
#   APLIKACE
# ======================
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",  start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip",    tip_cmd))
    app.add_handler(MessageHandler(filters.ALL, echo_all))
    return app

# ======================
#   MAIN
# ======================
def main():
    app = build_app()
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
