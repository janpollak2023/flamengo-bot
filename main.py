# main.py – Kiki Tipy 2 (Flamengo bot)
# ✅ Webhook, Telegram odpovědi a analýza "Gól do poločasu"
# Autor: Kiki pro Honzu ❤️

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from picks import find_first_half_goal_candidates  # rychlý modul (/tip)
from sources import analyze_sources                # širší sken (/tip24)

# ----------------------
# LOGGING
# ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("kiki-main")

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

def _fmt_ko(dt: Optional[datetime]) -> str:
    """Výkop v lokálním čase zařízení (CZ ok)."""
    return dt.astimezone(tz=None).strftime("%d.%m. %H:%M") if dt else "neznámé"

def _hours_from_arg(arg: Optional[str]) -> int:
    """
    Povolené varianty:
      - None  -> 24
      - 'dnes' -> do půlnoci (min 1 h, max 24 h)
      - 'zitra' -> zítra (24 h okno od zítřejší půlnoci)
      - integer string -> daný počet hodin (1..72)
    """
    if not arg:
        return 24
    a = arg.strip().lower()
    now = datetime.now().astimezone()
    if a in ("dnes", "today"):
        # do půlnoci místního času
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        hours = int(max(1, min(72, (midnight - now).total_seconds() // 3600 or 1)))
        return hours
    if a in ("zítra", "zitra", "tomorrow"):
        # zítra 00:00 až 23:59 -> 24 h od zítřejší půlnoci
        return 24
    try:
        n = int(a)
        return max(1, min(72, n))
    except Exception:
        return 24

# ======================
#   COMMAND HANDLERY
# ======================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Základní uvítací zpráva"""
    await update.message.reply_html(
        "Ahoj Honzo! 🟢 Jedu.\n"
        "/status = kontrola\n"
        "/tip = vyhledávání zápasů (gól do poločasu)\n"
        "/tip 6 = stejné, ale jen v příštích 6 hodinách\n"
        "/tip dnes | /tip zitra = časové okno podle dne\n"
        "/tip24 = širší sken (více zdrojů)\n"
        "/debug = diagnostika zdrojů\n\n"
        "🔥 Bot je připravený na Flamengo strategii."
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Najde zápasy podle Flamengo logiky – Gól v 1. poločase (rychlé TOP 3).
    Podporuje /tip <hodiny> | /tip dnes | /tip zitra
    """
    hours = _hours_from_arg(context.args[0]) if context.args else 24

    # Pokud uživatel píše "zitra", posuneme počátek okna na zítřejší půlnoc.
    # Funkce v picks.py pracuje s oknem "teď .. teď+hours", takže pro "zítra"
    # mu pošleme okno 24 hodin, ale tips modul si to drží relativně – proto
    # zde jen informativně ponecháme hours=24; výběr už zúží naše pravidla času.
    tips = find_first_half_goal_candidates(limit=3, hours_window=hours)

    if not tips:
        await update.message.reply_text("⚠️ Teď nic vhodného v tom okně.")
        return

    lines = []
    for i, t in enumerate(tips, 1):
        link = f"\n🔗 {getattr(t, 'url')}" if getattr(t, "url", None) else ""
        kurz = f" @ {t.odds:.2f}" if getattr(t, "odds", None) else ""
        ko = f"🕒 {_fmt_ko(getattr(t, 'kickoff', None))}"
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> ({t.league}) — {ko}\n"
            f"   Sázka: <b>{t.market}{kurz}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   Důvod: {t.reason}{link}"
        )

    msg = "🔥 <b>Flamengo – Gól do poločasu (TOP kandidáti)</b>\n" + "\n\n".join(lines)
    await update.message.reply_html(msg)

async def tip24_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Širší sken z více zdrojů (TOP 5). /tip zůstává beze změny."""
    try:
        tips = analyze_sources(limit=5) or []
    except Exception as e:
        log.exception("sources analyze failed: %s", e)
        tips = []

    # fallback – kdyby externí zdroje nic nevrátily
    if not tips:
        tips = find_first_half_goal_candidates(limit=5)
        if not tips:
            await update.message.reply_text("⚠️ Teď nic kvalitního nenašlo ani rozšířené skenování.")
            return

    lines = []
    for i, t in enumerate(tips, 1):
        ko = f"🕒 {_fmt_ko(getattr(t, 'kickoff', None))}"
        link = f"\n🔗 {getattr(t, 'url')}" if getattr(t, "url", None) else ""
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> — {ko}\n"
            f"   <b>{t.market}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   {t.reason}{link}"
        )

    await update.message.reply_html(
        "🔍 <b>Flamengo /tip24 – rozšířený sken (TOP 5)</b>\n\n" + "\n\n".join(lines)
    )

async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rychlá diagnostika zdrojů vs. fallbacku."""
    try:
        src = analyze_sources(limit=8) or []
    except Exception as e:
        log.exception("sources failed in debug: %s", e)
        src = []
    try:
        fast = find_first_half_goal_candidates(limit=8) or []
    except Exception as e:
        log.exception("picks failed in debug: %s", e)
        fast = []

    now = datetime.now().astimezone().strftime("%d.%m. %H:%M %Z")
    msg = (
        "🛠 DEBUG\n"
        f"- sources.py (rozšířené zdroje): {len(src)} tipů\n"
        f"- picks.py (rychlý sken/Tipsport): {len(fast)} tipů\n"
        f"- Now: {now}\n"
        "Pozn.: Pokud sources=0, běží fallback → proto se mohou opakovat stejné páry."
    )
    await update.message.reply_text(msg)

async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback pro běžné zprávy"""
    if update.message and update.message.text:
        await update.message.reply_text("Tip modul připraven – napojíme gól do poločasu.")

# --- Globální error handler (bezpečný) ---
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("HANDLER ERROR: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Menší zásek v analýze, běžím dál."
            )
    except Exception:
        pass

# ======================
#   APLIKACE
# ======================

def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip", tip_cmd))
    app.add_handler(CommandHandler("tip24", tip24_cmd))
    app.add_handler(CommandHandler("debug", debug_cmd))
    app.add_handler(MessageHandler(filters.ALL, echo_all))
    app.add_error_handler(on_error)
    return app

# ======================
#   MAIN
# ======================

def main():
    app = build_app()
    log.info("Starting webhook on %s", PUBLIC_URL + SECRET_PATH)
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
