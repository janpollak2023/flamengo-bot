# === main.py — Flamengo/Robstark tip bot (Replit 24/7) ===
# Replit -> Secrets: TELEGRAM_TOKEN, PORT=8080, ODDS_API_KEY
# Optional: SCAN_INTERVAL_MIN, CONFIDENCE_THRESHOLD, TOP_TIPS_PER_SCAN, DEFAULT_PROFILE

import os, asyncio, logging, threading, urllib.parse, requests, statistics, re, time
from typing import List, Dict, Optional

from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- ENV & LOG ----------
load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("betbot")

TOKEN = os.getenv("TELEGRAM_TOKEN")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
SCAN_INTERVAL_MIN = int(os.getenv("SCAN_INTERVAL_MIN", "10"))
CONF_THRESHOLD = int(os.getenv("CONFIDENCE_THRESHOLD", "85"))
TOP_TIPS_PER_SCAN = int(os.getenv("TOP_TIPS_PER_SCAN", "3"))
PROFILE_DEFAULT = os.getenv("DEFAULT_PROFILE",
                            "flamengo").lower().strip() or "flamengo"

# ---------- KEEP ALIVE (Flask) ----------
_app = Flask(__name__)


@_app.get("/")
def root():
    return "OK"


def _run_http():
    port = int(os.getenv("PORT", "8080"))
    _app.run(host="0.0.0.0", port=port)


def keep_alive():
    threading.Thread(target=_run_http, daemon=True).start()


# ---------- Tipsport link builder (bez scrapingu) ----------
def tipsport_search_link(home: str, away: str) -> str:
    q = urllib.parse.quote_plus(f"{home} {away}")
    return f"https://www.tipsport.cz/kurzy/vyhledavani?q={q}"


# ---------- Helpery ----------
def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def pct(i: float) -> int:
    return int(round(clamp(i, 0.0, 100.0)))


def median(vals: List[float]) -> float:
    try:
        return statistics.median(vals) if vals else 0.0
    except Exception:
        return 0.0


def parse_first_number(text: str) -> Optional[float]:
    m = re.search(r"(-?\d+(\.\d+)?)", text.replace(",", "."))
    return float(m.group(1)) if m else None


# ---------- “flagy” podle názvu trhu (bez externích dat) ----------
def infer_flags_from_market_name(sport: str, league: str, market: str) -> Dict:
    s = sport.lower()
    l = league.lower()
    m = market.lower()

    flags = {
        "is_halftime":
        any(k in m
            for k in ["ht/", "ht-ft", "half time", "1. poločas", "poločas"]),
        "is_yellow_cards":
        any(k in m for k in ["card", "žlut", "yellow"]),
        "is_corners":
        any(k in m for k in ["corner", "roh"]),
        "is_btts":
        any(k in m for k in
            ["btts", "both teams to score", "oba dají gól", "oba daji gol"]),
        "is_quarter":
        any(k in m for k in [
            "q1", "q2", "q3", "q4", "1q", "2q", "3q", "4q", "1. čtvrtina",
            "first quarter"
        ]),
        "is_first_goal":
        any(k in m
            for k in ["first goal", "first team to score", "první gól"]),
        "is_under":
        "under" in m or "méně" in m or "mene" in m,
        "is_over":
        "over" in m or "více" in m or "vice" in m,
        "line_number":
        parse_first_number(m),
        "is_wta": ("wta" in l),
        "is_tennis":
        s in ("tennis", "tenis"),
        "is_soccer":
        s in ("soccer", "fotbal"),
        "is_basket":
        s in ("basketball", "basket"),
        "is_ice":
        s in ("icehockey", "ice_hockey", "hokej"),
    }
    return flags


# ---------- Pravidla skórování ----------
def score_flamengo(t: Dict) -> int:
    """
    Flamengo pravidla:
      + preferuje OU/handicap/gamy; boost 2.10–3.50 (value outsider)
      + preferenční pásmo kurzu 1.50–2.20
      + boost HT/FT (trend) / BTTS / rohy / žluté / first goal (když trh indikuje)
      - penalizace favorit <1.50
      - WTA under <20 gamů tvrdě dolů
      - lehká penalizace “1Q over” u basketu (vyšší variance startu)
    """
    conf = float(t["base_confidence"])
    odds = float(t["odds"])
    flags = infer_flags_from_market_name(t["sport"], t.get("league", ""),
                                         t["market"])
    market = t["market"].lower()

    # preferované kurzy
    if 1.50 <= odds <= 2.20: conf += 5
    if odds < 1.50: conf -= 8
    if 2.10 <= odds <= 3.50: conf += 6
    elif odds > 3.50: conf += 3

    # OU/handicap/games -> boost
    if any(k in market for k in [
            "over", "under", "gamy", "games", "handicap", "spread", "eh", "ah",
            "+", "-"
    ]):
        conf += 4

    # WTA under <20
    if flags["is_tennis"] and flags["is_wta"] and flags["is_under"]:
        # pokus vytáhnout číselnou linii
        ln = flags["line_number"]
        if ln is not None and ln < 20:
            conf -= 12

    # Fotbal – HT/FT, BTTS, rohy, žluté
    if flags["is_soccer"]:
        if flags["is_halftime"]:
            conf += 6
        if flags["is_btts"]:
            conf += 5
        if flags["is_corners"] and flags["is_over"]:
            conf += 5
        if flags["is_yellow_cards"] and flags["is_over"]:
            conf += 5

    # Basket – čtvrtiny
    if flags["is_basket"] and flags["is_quarter"] and flags["is_over"]:
        conf -= 3  # konzervativně

    # Hokej – první gól
    if flags["is_ice"] and flags["is_first_goal"]:
        conf += 5

    return pct(conf)


def score_robstark(t: Dict) -> int:
    """
    Robstark styl:
      + preferuje 1.70–2.40
      + boost top ligy
      - penalizuje extrémy >4.0 a přestřelené OU
      + akceptuje BTTS / HTFT / corners / cards (když dostupné)
    """
    conf = float(t["base_confidence"])
    odds = float(t["odds"])
    league = t.get("league", "").lower()
    market = t["market"].lower()
    flags = infer_flags_from_market_name(t["sport"], league, market)

    if 1.70 <= odds <= 2.40: conf += 8
    if any(k in league for k in [
            "premier", "laliga", "bundes", "serie a", "ligue 1", "ucl", "uel",
            "atp", "wta", "nhl", "nba"
    ]):
        conf += 4
    if odds > 4.0: conf -= 8

    # přestřelené OU (futbalové “over 4.5/5.5/6.5” apod.)
    if "over" in market and any(f"{x}" in market
                                for x in ["4.5", "5.5", "6.5", "7.5"]):
        conf -= 6

    # BONUSY pro rozšířené trhy, když jsou dostupné
    if flags["is_btts"]: conf += 3
    if flags["is_halftime"]: conf += 3
    if flags["is_corners"] and flags["is_over"]: conf += 3
    if flags["is_yellow_cards"] and flags["is_over"]: conf += 3

    return pct(conf)


def score_by_profile(profile: str, tip: Dict) -> int:
    return score_flamengo(tip) if profile == "flamengo" else score_robstark(
        tip)


# ---------- Odds API: fetch & normalizace ----------
LEAGUE_HINTS = [
    "premier", "laliga", "bundes", "serie a", "ligue 1", "champions", "europa",
    "atp", "wta", "nhl", "nba"
]

# zkusíme víc market klíčů; backend si poradí s tím, co umí
MARKET_KEYS_PRIORITY = [
    "h2h,totals,spreads,btts", "h2h,totals,spreads", "h2h,totals", "h2h"
]


def fetch_events_from_oddsapi() -> List[Dict]:
    if not ODDS_API_KEY:
        log.warning("ODDS_API_KEY chybí – nebudu stahovat data.")
        return []

    out: List[Dict] = []
    endpoints = [("soccer", "eu"), ("tennis", "eu"), ("icehockey", "eu"),
                 ("basketball", "eu")]
    base = "https://api.the-odds-api.com/v4/sports"

    for sport, region in endpoints:
        data = None
        last_err = None
        for mk in MARKET_KEYS_PRIORITY:
            url = f"{base}/{sport}/odds/?regions={region}&markets={mk}&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    break
                else:
                    last_err = f"{r.status_code} {r.text[:180]}"
            except Exception as e:
                last_err = str(e)
        if data is None:
            log.warning(f"OddsAPI fail for {sport}: {last_err}")
            continue

        # normalize
        for g in data[:160]:  # safety limit
            home = g.get("home_team") or g.get("home")
            away = g.get("away_team") or g.get("away")
            if not home or not away:
                continue
            sport_title = g.get("sport_title", "")
            title_low = sport_title.lower()

            # lehký filtr na známé ligy u fotbalu (omezí bordel)
            if sport == "soccer" and not any(h in title_low
                                             for h in LEAGUE_HINTS):
                continue

            markets = {"h2h": [], "totals": [], "spreads": [], "btts": []}
            for bk in g.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    key = mk.get("key")
                    outcs = mk.get("outcomes", [])
                    for sel in outcs:
                        nm = sel.get("name", "") or ""
                        pt = sel.get("point")
                        # pro totals/spreads chceme vidět i linii
                        name = f"{nm} {pt}" if (pt is not None
                                                and key in ("totals",
                                                            "spreads")) else nm
                        price = sel.get("price")
                        try:
                            price = float(price)
                        except:
                            continue
                        if key in ("totals", "spreads", "h2h", "btts"):
                            markets["btts" if key == "btts" else key].append({
                                "name":
                                name,
                                "price":
                                price
                            })

            out.append({
                "sport": sport,
                "home": home,
                "away": away,
                "league": sport_title,
                "commence": g.get("commence_time", ""),
                "markets": markets
            })
    return out


def normalized_markets(markets: Dict) -> List[Dict]:
    out = []
    for key in ("totals", "spreads", "btts", "h2h"):
        for sel in markets.get(key, []):
            try:
                out.append({
                    "market": sel.get("name", ""),
                    "odds": float(sel["price"])
                })
            except Exception:
                pass
    return out


def make_best_tip_from_event(ev: Dict, profile: str) -> Optional[Dict]:
    cands = normalized_markets(ev.get("markets", {}))
    if not cands:
        return None

    best, best_score = None, -1
    base_conf = 82 if ev["sport"] in ("soccer", "icehockey",
                                      "basketball") else 80

    for c in cands:
        tip = {
            "id":
            f"{ev['sport']}|{ev['home']}|{ev['away']}|{c['market']}",
            "sport":
            "fotbal" if ev["sport"] == "soccer" else
            ("tenis" if ev["sport"] == "tennis" else ev["sport"]),
            "league":
            ev.get("league", ""),
            "match":
            f"{ev['home']} vs {ev['away']}",
            "market":
            c["market"],
            "pick":
            c["market"],
            "odds":
            c["odds"],
            "kickoff_iso":
            ev.get("commence", ""),
            "base_confidence":
            base_conf
        }
        sc = score_by_profile(profile, tip)
        if sc > best_score:
            best, best_score = tip, sc

    if best and best_score >= CONF_THRESHOLD:
        best["_score"] = best_score
        best["_tipsport"] = tipsport_search_link(ev["home"], ev["away"])
        return best
    return None


# ---------- Bot stav ----------
SUBSCRIBERS: List[int] = []
PAUSED = False
INTERVAL_MIN = SCAN_INTERVAL_MIN
SEEN_IDS: set[str] = set()
PROFILE = PROFILE_DEFAULT if PROFILE_DEFAULT in ("flamengo",
                                                 "robstark") else "flamengo"


# ---------- Telegram handlery ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if cid not in SUBSCRIBERS:
        SUBSCRIBERS.append(cid)
    await update.message.reply_text(
        "Ahoj! Flamengo/Robstark tip bot je připraven 🚀\n"
        "/tip – ruční scan\n"
        "/status – stav\n"
        "/interval <min> – změna intervalu\n"
        "/pause /resume – pauza/obnovení\n"
        "/profile <flamengo|robstark> – přepnutí pravidel\n"
        "/selftest – rychlý test Telegramu a OddsAPI")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Profil: {PROFILE}\n"
        f"Interval: {INTERVAL_MIN} min\n"
        f"Pauza: {'ANO' if PAUSED else 'NE'}\n"
        f"Odběratelé: {len(SUBSCRIBERS)}\n"
        f"Prah důvěry: {CONF_THRESHOLD}%\n"
        f"TOP tipů/scan: {TOP_TIPS_PER_SCAN}\n"
        f"OddsAPI klíč: {'OK' if bool(ODDS_API_KEY) else 'CHYBÍ'}")


async def interval_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global INTERVAL_MIN
    try:
        m = int(context.args[0])
        INTERVAL_MIN = max(1, m)
        await update.message.reply_text(
            f"Interval nastaven na {INTERVAL_MIN} min.")
    except Exception:
        await update.message.reply_text("Použití: /interval 10")


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PAUSED
    PAUSED = True
    await update.message.reply_text("Bot *pozastaven*.",
                                    parse_mode=ParseMode.MARKDOWN)


async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PAUSED
    PAUSED = False
    await update.message.reply_text("Bot *obnoven*.",
                                    parse_mode=ParseMode.MARKDOWN)


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PROFILE
    try:
        p = context.args[0].lower()
        if p in ("flamengo", "robstark"):
            PROFILE = p
            await update.message.reply_text(f"Profil přepnut na *{PROFILE}*.",
                                            parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                "Použití: /profile flamengo | /profile robstark")
    except Exception:
        await update.message.reply_text(
            "Použití: /profile flamengo | /profile robstark")


async def selftest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Telegram test
    telegram_ok = True
    try:
        await update.message.reply_text("🧪 Selftest: Telegram OK")
    except Exception as e:
        telegram_ok = False

    # OddsAPI test
    odds_ok = True
    try:
        url = f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}&all=true"
        r = requests.get(url, timeout=12)
        odds_ok = (r.status_code == 200)
    except Exception:
        odds_ok = False

    await update.message.reply_text(
        f"Selftest:\nTelegram: {'OK' if telegram_ok else 'FAIL'}\nOddsAPI: {'OK' if odds_ok else 'FAIL'}"
    )


async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 Hledám tipy…")
    await run_scan_once(context.application)


# ---------- Scan loop ----------
def format_tip_msg(t: Dict) -> str:
    return ("🔥 *TIP*\n"
            f"• *Zápas:* {t['match']}\n"
            f"• *Trh:* {t['market']}\n"
            f"• *Kurz:* {t['odds']:.2f}\n"
            f"• *Důvěra:* *{t['_score']}%*  _(profil: {PROFILE})_\n"
            f"• Tipsport: [Vyhledat zápas]({t['_tipsport']})")


async def run_scan_once(app: Application):
    if not ODDS_API_KEY:
        for cid in SUBSCRIBERS:
            try:
                await app.bot.send_message(
                    cid,
                    "❗ Chybí ODDS_API_KEY v Secrets. Přidej ho a dej /tip znovu."
                )
            except Exception:
                pass
        return

    events = fetch_events_from_oddsapi()
    tips: List[Dict] = []
    for ev in events:
        tip = make_best_tip_from_event(ev, PROFILE)
        if tip and tip["id"] not in SEEN_IDS:
            tips.append(tip)

    tips.sort(key=lambda x: x["_score"], reverse=True)
    tips = tips[:TOP_TIPS_PER_SCAN]

    if tips and SUBSCRIBERS:
        msg = "\n\n".join(format_tip_msg(t) for t in tips)
        for cid in SUBSCRIBERS:
            try:
                await app.bot.send_message(chat_id=cid,
                                           text=msg,
                                           parse_mode=ParseMode.MARKDOWN,
                                           disable_web_page_preview=True)
            except Exception as e:
                log.warning(f"Send fail {cid}: {e}")
        for t in tips:
            SEEN_IDS.add(t["id"])
    else:
        log.info("Žádné tipy k odeslání.")


async def scan_loop(app: Application):
    while True:
        try:
            if not PAUSED and SUBSCRIBERS:
                await run_scan_once(app)
            await asyncio.sleep(INTERVAL_MIN * 60)
        except Exception as e:
            log.error(f"Scan loop err: {e}")
            await asyncio.sleep(10)


# ---------- Start ----------
def main():
    if not TOKEN:
        raise RuntimeError("Chybí TELEGRAM_TOKEN v Secrets.")
    keep_alive()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("status", status_cmd))
    application.add_handler(CommandHandler("interval", interval_cmd))
    application.add_handler(CommandHandler("pause", pause_cmd))
    application.add_handler(CommandHandler("resume", resume_cmd))
    application.add_handler(CommandHandler("profile", profile_cmd))
    application.add_handler(CommandHandler("selftest", selftest_cmd))
    application.add_handler(CommandHandler("tip", tip_cmd))

    asyncio.get_event_loop().create_task(scan_loop(application))
    log.info("Bot běží…")
    application.run_polling(drop_pending_updates=True, stop_signals=None)


if __name__ == "__main__":
    main()
