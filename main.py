# main.py – Kiki Tipy 2 (Flamengo bot)
# ✅ Webhook, Telegram odpovědi a analýza "Gól do poločasu"
# Autor: Kiki pro Honzu ❤️

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List

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

def _parse_tip_window(arg: Optional[str]) -> Tuple[datetime, datetime, str]:
    """
    Vrátí (start, end, popis) časového okna pro filtrování tipů.
    Podporuje:
      /tip           -> teď .. +24 h
      /tip 6         -> teď .. +6 h
      /tip dnes      -> teď .. dnešní půlnoc
      /tip zitra     -> zítřek 00:00 .. zítřek 23:59
    """
    now = datetime.now().astimezone()
    label = "24 h"
    if not arg:
        return now, now + timedelta(hours=24), label

    a = arg.strip().lower()
    if a in ("dnes", "today"):
        midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        label = "dnes"
        return now, midnight, label

    if a in ("zítra", "zitra", "tomorrow"):
        start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        label = "zítra"
        return start, end, label

    try:
        hours = max(1, min(72, int(a)))
        label = f"{hours} h"
        return now, now + timedelta(hours=hours), label
    except Exception:
        return now, now + timedelta(hours=24), "24 h"

def _filter_by_window(tips: List, start: datetime, end: datetime) -> List:
    out = []
    for t in tips:
        ko = getattr(t, "kickoff", None)
        if ko is None:
            # když neznáme výkop, ponecháme (ať máme z čeho vybírat)
            out.append(t)
            continue
        if start <= ko.astimezone(start.tzinfo) < end:
            out.append(t)
    return out

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
    # 1) časové okno z argumentu
    start, end, label = _parse_tip_window(context.args[0] if context.args else None)

    # 2) vezmeme širší set kandidátů a pak ho ořízneme na časové okno
    #    (picks.py vrací už seřazené podle confidence a času).
    base = find_first_half_goal_candidates(limit=16) or []
    tips = _filter_by_window(base, start, end)

    if not tips:
        await update.message.reply_text(f"⚠️ V okně „{label}“ jsem nic vhodného nenašla.")
        return

    # finální TOP 3 po filtrování
    tips = tips[:3]

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

    msg = (
        "🔥 <b>Flamengo – Gól do poločasu (TOP kandidáti)</b>\n"
        + "\n\n".join(lines)
    )
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
        tips = find_first_half_goal_candidates(limit=8)
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
        fast = find_first_half_goal_candidates(limit=12) or []
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
