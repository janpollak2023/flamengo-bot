# main.py – Kiki Tipy 2 (Flamengo bot)
# ✅ Webhook, Telegram odpovědi a analýza "Gól do poločasu"
# Autor: Kiki pro Honzu ❤️

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple, Set

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from picks import find_first_half_goal_candidates   # rychlý modul
from sources import analyze_sources                 # širší sken (/tip24)

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

TZ = timezone(timedelta(hours=1))

# ======================
#   RUNTIME ANTI-DUP (na den)
# ======================
_SENT: dict = {"date": None, "keys": set()}  # type: ignore[assignment]

def _maybe_reset_daily():
    today = datetime.now(TZ).date()
    if _SENT["date"] != today:
        _SENT["date"] = today
        _SENT["keys"] = set()  # type: ignore[assignment]

def _seen(key: str) -> bool:
    _maybe_reset_daily()
    s: Set[str] = _SENT["keys"]  # type: ignore[assignment]
    if key in s:
        return True
    s.add(key)
    return False

# ======================
#   HELPERS
# ======================

def _fmt_ko(dt: Optional[datetime]) -> str:
    """Výkop v CZ čase."""
    return dt.astimezone(TZ).strftime("%d.%m. %H:%M") if dt else "neznámé"

def _filter_by_window_and_conf(
    tips: List,
    start_dt: datetime,
    end_dt: datetime,
    min_conf: int = 90,
) -> List:
    out = []
    for t in tips:
        ko = getattr(t, "kickoff", None)
        conf = int(getattr(t, "confidence", 0) or 0)
        if conf < min_conf:
            continue
        if ko is None:
            continue
        ko_cz = ko.astimezone(TZ)
        if start_dt <= ko_cz < end_dt:
            out.append(t)
    # seřaď po filtru (vyšší důvěra, dřívější KO)
    out.sort(key=lambda x: (-int(getattr(x, "confidence", 0) or 0),
                            getattr(x, "kickoff").timestamp() if getattr(x, "kickoff", None) else 1e15))
    return out

def _render_lines(tips: List) -> str:
    lines = []
    for i, t in enumerate(tips, 1):
        ko = f"🕒 <b>{_fmt_ko(getattr(t, 'kickoff', None))}</b>"
        kurz = f" @ {t.odds:.2f}" if getattr(t, "odds", None) else ""
        link = f"\n🔗 {getattr(t, 'url')}" if getattr(t, 'url', None) else ""
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> ({t.league}) — {ko}\n"
            f"   <b>{t.market}{kurz}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   {t.reason}{link}"
        )
    return "\n\n".join(lines)

async def _run_tip_window(
    update: Update,
    window_label: str,
    hours_from: int,
    hours_to: int,
    limit: int = 5,
):
    """Společná obsluha pro /tip, /tip2, /tip3."""
    now = datetime.now(TZ)
    start_dt = now + timedelta(hours=hours_from)
    end_dt = now + timedelta(hours=hours_to)

    try:
        # vezmeme širší sadu, picks.py už umí hours_window (pojistka 36 h)
        base = find_first_half_goal_candidates(limit=48, hours_window=36) or []
    except Exception as e:
        log.exception("picks failed: %s", e)
        await update.message.reply_text("⚠️ Přerušení při čtení zdrojů.")
        return

    tips = _filter_by_window_and_conf(base, start_dt, end_dt, min_conf=90)

    # anti-dup (match+kickoff v CZ)
    fresh = []
    for t in tips:
        ko = getattr(t, "kickoff", None)
        key = f"{getattr(t,'match','')}|{ko.astimezone(TZ).strftime('%Y-%m-%d %H:%M') if ko else ''}"
        if not _seen(key):
            fresh.append(t)
        if len(fresh) >= limit:
            break

    if not fresh:
        await update.message.reply_html(f"⚠️ V okně „<b>{window_label}</b>“ jsem nic vhodného nenašla.")
        return

    await update.message.reply_html(f"🔥 <b>Flamengo – Gól do poločasu</b> ({window_label})\n\n" + _render_lines(fresh))

# ======================
#   COMMAND HANDLERY
# ======================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "Ahoj Honzo! 🟢 Jedu.\n"
        "/status = kontrola\n"
        "/tip  = 1–3 h (gól do poločasu)\n"
        "/tip2 = 8–12 h\n"
        "/tip3 = 12–24 h\n"
        "/tip24 = širší sken (více zdrojů)\n"
        "/debug = diagnostika zdrojů\n\n"
        "🔥 Bot je připravený na Flamengo strategii."
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

# /tip → 1–3 hodiny
async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_tip_window(update, "1–3 h", 1, 3, limit=5)

# /tip2 → 8–12 hodin
async def tip2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_tip_window(update, "8–12 h", 8, 12, limit=5)

# /tip3 → 12–24 hodin
async def tip3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_tip_window(update, "12–24 h", 12, 24, limit=5)

async def tip24_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Širší sken z více zdrojů (TOP 5)."""
    try:
        tips = analyze_sources(limit=5) or []
    except Exception as e:
        log.exception("sources analyze failed: %s", e)
        tips = []

    if not tips:
        tips = find_first_half_goal_candidates(limit=8, hours_window=36) or []

    if not tips:
        await update.message.reply_text("⚠️ Teď nic kvalitního nenašlo ani rozšířené skenování.")
        return

    await update.message.reply_html("🔍 <b>Flamengo /tip24 – rozšířený sken (TOP 5)</b>\n\n" + _render_lines(tips[:5]))

async def debug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        src = analyze_sources(limit=8) or []
    except Exception as e:
        log.exception("sources failed in debug: %s", e)
        src = []
    try:
        fast = find_first_half_goal_candidates(limit=12, hours_window=36) or []
    except Exception as e:
        log.exception("picks failed in debug: %s", e)
        fast = []

    now = datetime.now(TZ).strftime("%d.%m. %H:%M %Z")
    msg = (
        "🛠 DEBUG\n"
        f"- sources.py (rozšířené zdroje): {len(src)} tipů\n"
        f"- picks.py (rychlý sken): {len(fast)} tipů\n"
        f"- Now: {now}\n"
        "Pozn.: Anti-dup blokuje opakování v rámci dne."
    )
    await update.message.reply_text(msg)

async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text("Tip modul připraven – gól do poločasu.")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("HANDLER ERROR: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="⚠️ Menší zásek v analýze, běžím dál.")
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
    app.add_handler(CommandHandler("tip2", tip2_cmd))
    app.add_handler(CommandHandler("tip3", tip3_cmd))
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
