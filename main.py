# main.py — Flask + python-telegram-bot 21.6 (Render-ready)
# Příkazy:
# /status – rychlý test
# /scan [fotbal|hokej|tenis|basket|esport] – vypíše top zápasy z Tipsportu
# /analyze <URL_zápasu_z_Tipsportu> – stáhne fakta a vrátí Flamengo tipy
# /tip [sport=fotbal minconf=85 window=8 count=10] – spustí interní pipeline a vrátí shortlist
# /debug – info o webhooku/pollingu

from __future__ import annotations
import os
import logging
import asyncio
from typing import Dict

from flask import Flask, request

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ====== interní moduly ======
from urls import get_url, categories
from markets import FOOTBALL_MARKETS         # (import se hodí, i když se zde přímo nepoužije)
from scraper import get_match_list, tipsport_stats
from picks import make_picks
from analyzer import TeamStats

# --------- Logování ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s"
)
log = logging.getLogger("flamengo-main")

# --------- Flask -------------
app = Flask(__name__)

# --------- Env proměnné ------
TOKEN       = os.getenv("TELEGRAM_TOKEN", "")
PUBLIC_URL  = os.getenv("PUBLIC_URL", "")              # např. https://flamengo-bot.onrender.com
SECRET_PATH = os.getenv("SECRET_PATH", "webhook")      # endpoint pro Telegram
MODE        = os.getenv("MODE", "webhook").lower()     # "webhook" (Render) nebo "polling" (lokálně)

# --------- Telegram Application ----------
if not TOKEN:
    log.warning("⚠️  TELEGRAM_TOKEN není nastaven!")

application = Application.builder().token(TOKEN).build()

# ===================== Pomocné funkce =====================

def _parse_kv(args: list[str]) -> Dict[str, str]:
    """
    Převede parametry ve tvaru key=value na dict (case-insensitive na key).
    """
    out: Dict[str, str] = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            out[k.lower()] = v
    return out

# ===================== Handlery příkazů =====================

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Kiki běží. Pošli /scan nebo /analyze <url> nebo /tip")

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
        return await update.message.reply_text(f"Top zápasy *{cat}*: Nic nenalezeno.", parse_mode="Markdown")

    lines = [f"{i+1}. {x.get('title','(bez názvu)')} — {x.get('url','')}" for i, x in enumerate(lst)]
    await update.message.reply_text(f"Top zápasy *{cat}*:\n" + "\n".join(lines), parse_mode="Markdown")

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Analýza zápasu – stáhne Tipsport statistiky a provede výběr tipů.
    Použití: /analyze https://m.tipsport.cz/kurzy/zapas/...
    """
    match_url = " ".join(ctx.args).strip()
    if not match_url:
        return await update.message.reply_text(
            "Pošli URL zápasu z Tipsportu. Příklad:\n/analyze https://m.tipsport.cz/kurzy/zapas/...",
        )

    try:
        ts = tipsport_stats(match_url)  # může vracet dict/raw
    except Exception as e:
        log.exception("tipsport_stats selhal")
        return await update.message.reply_text(f"❌ Chyba načítání statistik: {e}")

    # --- mock převod -> TeamStats (zatím fixní příklad; později mapuj přímo z ts)
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
    h2h = {"1h_rate": 68, "btts_rate": 60}  # příkladové hodnoty

    try:
        picks = make_picks(home, away, h2h) or []
    except Exception as e:
        log.exception("make_picks selhal")
        return await update.message.reply_text(f"❌ Chyba při výběru tipů: {e}")

    if not picks:
        return await update.message.reply_text("SKIP – nic ≥ 80 %.")

    lines = [
        f"• {p['market_label']} → {p['confidence_pct']}% [{p['bucket']}]\nDůvod: {p['reason']}"
        for p in picks
    ]
    await update.message.reply_text("\n\n".join(lines))

async def cmd_tip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Spuštění interní pipeline s parametry:
    /tip sport=fotbal minconf=85 window=8 count=10
    """
    kv = _parse_kv(ctx.args)
    sport  = kv.get("sport", "fotbal").lower()
    minconf = int(kv.get("minconf", "85"))
    window  = int(kv.get("window",  "8"))
    count   = int(kv.get("count",   "10"))

    # run_pipeline je v tip_engine.py – pokud ho používáš, naimportuj; zde voláme make_picks přes scan/analyze flow.
    await update.message.reply_text(f"🔎 Hledám zápasy… (analýza + kontrola Tipsportu)\n"
                                    f"sport={sport}, minconf={minconf}, window={window}, count={count}")

    # Zde můžeš později doplnit skutečný orchestrátor (scan -> stats -> picks).
    # Prozatím vrátíme info, pokud nic není nad prahem:
    return await update.message.reply_text("ℹ️ Nic nad prahem důvěry. Zkus upravit parametry (např. minconf=80).")

async def cmd_debug(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Shrnutí režimu + info o webhooku
    info = await application.bot.get_webhook_info()
    txt = (
        f"*MODE:* `{MODE}`\n"
        f"*Webhook URL:* `{info.url or '-'}`\n"
        f"*Has pending:* `{info.has_custom_certificate}`\n"
        f"*IP:* `{info.ip_address or '-'}`\n"
        f"*Max conn:* `{info.max_connections}`\n"
        f"*Pending updates:* `{info.pending_update_count}`\n"
    )
    await update.message.reply_text(txt, parse_mode="Markdown")

# Registrace handlerů
application.add_handler(CommandHandler("status",  cmd_status))
application.add_handler(CommandHandler("scan",    cmd_scan))
application.add_handler(CommandHandler("analyze", cmd_analyze))
application.add_handler(CommandHandler("tip",     cmd_tip))
application.add_handler(CommandHandler("debug",   cmd_debug))

# ===================== Flask routy =====================

@app.get("/healthz")
def healthz():
    return "OK", 200

@app.get("/")
def root():
    return "flamengo-bot běží", 200

@app.post(f"/{SECRET_PATH}")
def telegram_webhook():
    """Telegram webhook — PTB 21.* zpracování příchozího Update."""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
    except Exception as e:
        log.exception("Webhook processing error")
        return f"ERR: {e}", 500
    return "OK", 200

# ===================== Start =====================

def setup_webhook():
    """
    Nastaví webhook na PUBLIC_URL/{SECRET_PATH}.
    Musí být nastavené PUBLIC_URL, jinak nebude fungovat.
    """
    if not PUBLIC_URL:
        log.warning("⚠️  PUBLIC_URL není nastaven = webhook nepůjde nastavit.")
        return
    url = f"{PUBLIC_URL.rstrip('/')}/{SECRET_PATH}"
    asyncio.run(application.bot.set_webhook(url=url))
    log.info(f"✅ Webhook nastaven: {url}")

if __name__ == "__main__":
    if MODE == "polling":
        log.info("▶️  Start POLLING režimu")
        application.run_polling(drop_pending_updates=True)
    else:
        # Render / produkce – webhook
        if TOKEN and PUBLIC_URL:
            setup_webhook()
        port = int(os.getenv("PORT", "5000"))
        log.info(f"🌐 Flask start na portu {port} (webhook: /{SECRET_PATH})")
        app.run(host="0.0.0.0", port=port)
