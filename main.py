# main.py – Flask + python-telegram-bot 21.6 (Render-ready)
# Příkazy:
#  /status  – rychlý test
#  /scan [fotbal|hokej|tenis|basket|esport] – vypíše top zápasy z Tipsportu
#  /analyze <URL_zápasu_z_Tipsportu> – udělá Flamengo analýzu a návrhy tipů

from __future__ import annotations

import os
import asyncio
import logging
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)

# === interní moduly ===
from urls import get_url, categories           # uložené URL Tipsportu
from markets import FOOTBALL_MARKETS           # zatím jen kvůli importu (příp. validace)
from scraper import get_match_list, tipsport_stats
from picks import make_picks
from analyzer import TeamStats

# ------------ Logování ------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("flamengo-main")

# ------------ Flask ------------
app = Flask(__name__)

# ------------ Env proměnné ------------
TOKEN = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "")          # např. https://flamengo-bot.onrender.com
SECRET_PATH = os.getenv("SECRET_PATH", "webhook") # /<SECRET_PATH> je webhook endpoint
MODE = os.getenv("MODE", "webhook").lower()       # "webhook" (Render) nebo "polling" (lokálně)

if not TOKEN:
    log.warning("⚠️ TELEGRAM_TOKEN není nastaven!")

# ------------ Telegram Application ------------
application = Application.builder().token(TOKEN).build()


# ========== HANDLERY ==========
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Kiki běží. Pošli /scan nebo /analyze <url>.")


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Vytáhne top zápasy pro zadanou kategorii (default fotbal) z uložených URL."""
    cat = (ctx.args[0] if ctx.args else "fotbal").lower()
    url = get_url(cat)

    try:
        lst = (get_match_list(url) or [])[:12]
    except Exception as e:
        log.exception("get_match_list selhal")
        return await update.message.reply_text(f"❌ Chyba načítání zápasů: {e}")

    if not lst:
        return await update.message.reply_text(f"Top zápasy {cat}: Nic nenalezeno.")

    lines = [f"• {i+1}. {x.get('title','(bez názvu)')}" for i, x in enumerate(lst)]
    await update.message.reply_text(f"Top zápasy {cat}:\n" + "\n".join(lines))


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Analýza zápasu – zatím mock TeamStats, reálné stats dodá scraper.tipsport_stats."""
    match_url = " ".join(ctx.args).strip()
    if not match_url:
        return await update.message.reply_text("Pošli URL zápasu z Tipsportu. Příklad: /analyze https://m.tipsport.cz/kurzy/zapas/…")

    try:
        ts = tipsport_stats(match_url)   # zatím klidně vrací dict/raw – níže je mock převod
    except Exception as e:
        log.exception("tipsport_stats selhal")
        return await update.message.reply_text(f"❌ Chyba načítání statistik: {e}")

    # TODO: převést `ts` → skutečné TeamStats (mapování z tipsport_stats)
    home = TeamStats(
        form5_pts=10, gf_pg=2.1, ga_pg=0.9,
        first_half_goal_rate=72, btts_rate=58,
        injuries_key=0, home_adv=True,
    )
    away = TeamStats(
        form5_pts=5, gf_pg=1.2, ga_pg=1.6,
        first_half_goal_rate=61, btts_rate=55,
        injuries_key=1, home_adv=False,
    )
    h2h = {"1H_rate": 68, "btts_rate": 60}

    try:
        picks = make_picks(home, away, h2h) or []
    except Exception as e:
        log.exception("make_picks selhal")
        return await update.message.reply_text(f"❌ Chyba při výběru tipů: {e}")

    if not picks:
        return await update.message.reply_text("SKIP – nic ≥80 %.")

    lines = [
        f"🎯 {p['market_label']} — {p['confidence_pct']}% [{p['bucket']}]\n• Důvod: {p['reason']}"
        for p in picks
    ]
    await update.message.reply_text("\n\n".join(lines))


async def cmd_cats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Pro kontrolu – vypíše uložené kategorie a jejich URL."""
    cats = categories()
    lines = [f"{k}: {v}" for k, v in cats.items()]
    await update.message.reply_text("Kategorie → URL:\n" + "\n".join(lines))


# Registrace handlerů
application.add_handler(CommandHandler("status", cmd_status))
application.add_handler(CommandHandler("scan",   cmd_scan))
application.add_handler(CommandHandler("analyze", cmd_analyze))
application.add_handler(CommandHandler("cats",    cmd_cats))


# ========== FLASK ROUTY ==========
@app.get("/healthz")
def healthz():
    return "OK", 200


@app.get("/")
def root():
    return "🏠 Flamengo bot běží", 200


@app.post(f"/{SECRET_PATH}")
def telegram_webhook():
    """Telegram webhook – PTB 21.* zpracování příchozího Update."""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run(application.process_update(update))
    except Exception as e:
        log.exception("Webhook processing error")
        return f"ERR: {e}", 500
    return "OK", 200


# ========== START ==========
def setup_webhook():
    if not PUBLIC_URL:
        log.warning("PUBLIC_URL není nastaven – webhook nepůjde nastavit.")
        return
    url = f"{PUBLIC_URL.rstrip('/')}/{SECRET_PATH}"
    asyncio.run(application.bot.set_webhook(url=url))
    log.info(f"✅ Webhook nastaven: {url}")


if __name__ == "__main__":
    if MODE == "polling":
        # Lokální běh bez webhooku
        log.info("▶️ Start POLLING režimu")
        application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    else:
        # Render / produkce – webhook
        if TOKEN:
            setup_webhook()
        port = int(os.getenv("PORT", "5000"))
        log.info(f"🌐 Flask start na portu {port} (webhook: /{SECRET_PATH})")
        app.run(host="0.0.0.0", port=port)
# main.py (doplň import)
from tip_engine import run_pipeline

def _parse_kv(args):
    out = {}
    for a in args:
        if "=" in a:
            k,v = a.split("=",1)
            out[k.lower()] = v
    return out

async def cmd_tip(update, ctx):
    kv = _parse_kv(ctx.args)
    sport   = kv.get("sport", "fotbal").lower()
    minconf = int(kv.get("minconf", "85"))
    window  = int(kv.get("window",  "8"))
    count   = int(kv.get("count",   "10"))

    await update.message.reply_text("🔎 Hledám zápasy… (analýza + kontrola Tipsport)")
    tips = run_pipeline(sport=sport, minconf=minconf, window_h=window, max_count=count)

    if not tips:
        return await update.message.reply_text("ℹ️ Nic nad prahem důvěry. Zkus upravit parametry (např. minconf/window).")

    lines = []
    for t in tips:
        # TipCandidate vs dict – ošetříme obě varianty
        label = getattr(t, "market_label", None) or t.get("market_label", "")
        conf  = getattr(t, "confidence", None) or t.get("confidence_pct", 0)
        buck  = getattr(t, "bucket", None) or t.get("bucket", "")
        reas  = getattr(t, "reason", None) or t.get("reason", "")
        lines.append(f"🎯 {label} — {int(conf)}% [{buck}]\n• Důvod: {reas}")

    await update.message.reply_text("\n\n".join(lines))

# registrace
application.add_handler(CommandHandler("tip", cmd_tip))
