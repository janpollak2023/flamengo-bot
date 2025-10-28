# main.py – Kiki Tipy 2 (Flamengo bot)
# ✅ Webhook, Telegram odpovědi a analýza "Gól do poločasu"
# Autor: Kiki pro Honzu ❤️

import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from picks import find_first_half_goal_candidates  # rychlý modul (/tip)
from sources import analyze_sources                 # širší sken (/tip24)

# ======================
#   ENVIRONMENT
# ======================
TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
SECRET_PATH = os.getenv("SECRET_PATH", "/tvuj_tajny_hook").strip()
if not SECRET_PATH.startswith("/"):
    SECRET_PATH = "/" + SECRET_PATH
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET", "").strip()
PORT = int(os.getenv("PORT", "10000"))

# ======================
#   HELPERS
# ======================

def _fmt_ko(dt: datetime | None) -> str:
    """Výkop v lokálním čase zařízení (CZ ok)."""
    return dt.astimezone(tz=None).strftime("%d.%m. %H:%M") if dt else "neznámé"

# ======================
#   COMMAND HANDLERY
# ======================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Základní uvítací zpráva"""
    await update.message.reply_html(
        "Ahoj Honzo! 🟢 Jedu.\n"
        "/status = kontrola\n"
        "/tip = vyhledávání zápasů (gól do poločasu)\n"
        "/tip24 = širší sken (více zdrojů)\n"
        "/debug = diagnostika zdrojů\n\n"
        "🔥 Bot je připravený na Flamengo strategii."
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vrací stav bota"""
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Najde zápasy podle Flamengo logiky – Gól v 1. poločase (rychlé TOP 3)"""
    tips = find_first_half_goal_candidates(limit=3)

    if not tips:
        await update.message.reply_text("⚠️ Momentálně žádné zápasy nenalezeny.")
        return

    lines = []
    for i, t in enumerate(tips, 1):
        link = f"\n🔗 {t.url}" if getattr(t, "url", None) else ""
        kurz = f" @ {t.odds:.2f}" if getattr(t, "odds", None) else ""
        ko = f"🕒 {_fmt_ko(getattr(t, 'kickoff', None))}"
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> ({t.league}) — {ko}\n"
            f"   Sázka: <b>{t.market}{kurz}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   Důvod: {t.reason}{link}"
        )

    msg = (
        "🔥 <b>Flamengo – Gól do poločasu (TOP kandidáti)</b>\n"
        + "\n\n".join(lines)
        + "\n\n"
        "Pozn.: Pokud Tipsport blokuje přístup, bot vrátí fallback návrhy.\n"
        "V další verzi přidáme přesné kurzy a statistiky z detailů zápasů. ⚙️"
    )
    await update.message.reply_html(msg)

async def tip24_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Širší sken z více zdrojů (TOP 5). /tip zůstává beze změny."""
    tips = analyze_sources(limit=5)

    # fallback – kdyby externí zdroje nic nevrátily
    if not tips:
        tips = find_first_half_goal_candidates(limit=5)
        if not tips:
            await update.message.reply_text("⚠️ Teď nic kvalitního nenašlo ani rozšířené skenování.")
            return

    lines = []
    for i, t in enumerate(tips, 1):
        ko = f"🕒 {_fmt_ko(getattr(t, 'kickoff', None))}"
        link = f"\n🔗 {t.url}" if getattr(t, "url", None) else ""
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> — {ko}\n"
            f"   <b>{t.market}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   {t.reason}{link}"
        )

    await update.message.reply_html(
        "🔍 <b>Flamengo /tip24 – rozšířený sken (TOP 5)</b>\n\n" + "\n\n".join(lines)
    )

# --- DEBUG: ukáže, kolik tipů vrátily reálné zdroje vs. fallback ---
async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        src = analyze_sources(limit=8) or []
    except Exception as e:
        src = []
    try:
        fast = find_first_half_goal_candidates(limit=8) or []
    except Exception as e:
        fast = []

    now = datetime.now().astimezone().strftime("%d.%m. %H:%M %Z")
    msg = (
        "🛠 DEBUG\n"
        f"- sources.py (rozšířené zdroje): {len(src)} tipů\n"
        f"- picks.py (rychlý sken/Tipsport): {len(fast)} tipů\n"
        f"- Now: {now}\n"
        "Pozn.: Pokud sources=0, běží fallback → proto se opakují stejné páry."
    )
    await update.message.reply_text(msg)

async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback pro běžné zprávy"""
    if update.message and update.message.text:
        await update.message.reply_text("Tip modul připraven – napojíme gól do poločasu.")

# ======================
#   APLIKACE
# ======================

def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip", tip_cmd))
    app.add_handler(CommandHandler("tip24", tip24_cmd))
    app.add_handler(CommandHandler("debug", debug_cmd))  # ✅ přidáno
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
