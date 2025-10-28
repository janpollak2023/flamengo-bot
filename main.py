# main.py – Kiki Tipy 2 (Flamengo bot) – TIPSPORT ONLY windows
import os, logging
from datetime import datetime, timedelta
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from picks import find_tipsport_ht_candidates  # << NOVÉ: jen Tipsport

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kiki-main")

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
SECRET_PATH = os.getenv("SECRET_PATH", "/tvuj_tajny_hook").strip()
if not SECRET_PATH.startswith("/"): SECRET_PATH = "/" + SECRET_PATH
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET", "").strip()
PORT = int(os.getenv("PORT", "10000"))

# --- anti-dup: paměť už poslaných tipů v daný den ---
SENT_KEYS: set[str] = set()
SENT_DATE: Optional[str] = None

def _roll_day():
    global SENT_KEYS, SENT_DATE
    today = datetime.now().date().isoformat()
    if SENT_DATE != today:
        SENT_KEYS = set()
        SENT_DATE = today

def _fmt(dt: Optional[datetime]) -> str:
    return dt.astimezone().strftime("%d.%m. %H:%M") if dt else "neznámé"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(
        "Ahoj Honzo! 🟢 Kiki Tipy 2 (Tipsport-only).\n"
        "/status = kontrola\n"
        "/tip  → okno 1–3 h od teď\n"
        "/tip2 → okno 8–12 h od teď\n"
        "/tip3 → okno 12–24 h od teď\n"
        "Pravidla: jen fotbal, trh Gól v 1. poločase: ANO, důvěra 90 %, bez opakování.\n"
        "🔥 Flamengo režim aktivní."
    )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Alive – webhook OK, bot běží.")

# --- společný vykreslovač ---
async def _send_tips(update: Update, tips, tag: str):
    if not tips:
        await update.message.reply_text("⚠️ Nic vhodného v zadaném okně.")
        return

    lines = []
    for i, t in enumerate(tips, 1):
        ko = f"🕒 {_fmt(getattr(t, 'kickoff', None))}"
        link = f"\n🔗 {getattr(t, 'url')}" if getattr(t, 'url', None) else ""
        lines.append(
            f"#{i} ⚽ <b>{t.match}</b> — {ko}\n"
            f"   <b>{t.market}</b>\n"
            f"   Důvěra: <b>{t.confidence}%</b> | Okno: <b>{t.window}</b>\n"
            f"   {t.reason}{link}"
        )
    await update.message.reply_html(f"📊 <b>{tag} – Tipsport (HT goal)</b>\n\n" + "\n\n".join(lines))

# --- 3 příkazy s okny a anti-dup ---
async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _roll_day()
    tips = find_tipsport_ht_candidates(start_offset_h=1, end_offset_h=3, min_conf=90, exclude_keys=SENT_KEYS, limit=5)
    SENT_KEYS.update(t.key for t in tips)
    await _send_tips(update, tips[:3], "TIP (1–3 h)")

async def tip2_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _roll_day()
    tips = find_tipsport_ht_candidates(start_offset_h=8, end_offset_h=12, min_conf=90, exclude_keys=SENT_KEYS, limit=5)
    SENT_KEYS.update(t.key for t in tips)
    await _send_tips(update, tips[:3], "TIP2 (8–12 h)")

async def tip3_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _roll_day()
    tips = find_tipsport_ht_candidates(start_offset_h=12, end_offset_h=24, min_conf=90, exclude_keys=SENT_KEYS, limit=6)
    SENT_KEYS.update(t.key for t in tips)
    await _send_tips(update, tips[:3], "TIP3 (12–24 h)")

async def echo_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        await update.message.reply_text("Použij /tip, /tip2, /tip3 (Tipsport, gól do poločasu).")

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("HANDLER ERROR: %s", context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(update.effective_chat.id, "⚠️ Menší zásek v analýze, běžím dál.")
    except Exception:
        pass

def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("tip", tip_cmd))
    app.add_handler(CommandHandler("tip2", tip2_cmd))
    app.add_handler(CommandHandler("tip3", tip3_cmd))
    app.add_handler(MessageHandler(filters.ALL, echo_all))
    app.add_error_handler(on_error)
    return app

def main():
    app = build_app()
    app.run_webhook(
        listen="0.0.0.0", port=int(os.getenv("PORT", "10000")),
        url_path=SECRET_PATH.lstrip("/"),
        webhook_url=f"{PUBLIC_URL}{SECRET_PATH}",
        secret_token=SECRET_TOKEN if SECRET_TOKEN else None,
        allowed_updates=["message","edited_message","callback_query"],
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
