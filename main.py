import os, re, json, logging, traceback, hashlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, JobQueue, filters
)

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s | %(name)s: %(message)s")
log = logging.getLogger("bot")

# ---------------- ENV & TOKEN ----------------
RAW = os.getenv("TELEGRAM_TOKEN", "")
TOKEN = re.sub(r"[^A-Za-z0-9:_-]", "", RAW)  # očista neviditelných znaků
if TOKEN != RAW:
    log.warning("Token cleaned of hidden characters.")
log.info(f"FINGERPRINT: ***{TOKEN[-6:]}")

MIN_CONF = float(os.getenv("MIN_CONF", "85"))   # minimální důvěra pro výstup
MAX_TIPS = int(os.getenv("MAX_TIPS", "6"))      # max počet tipů, které pipeline vrátí

# ---------------- SAFE IMPORT VOLITELNÝCH MODULŮ ----------------
def _safe_import(name: str):
    try:
        return __import__(name)
    except Exception:
        log.info(f"Module '{name}' not available.")
        return None

tip_engine       = _safe_import("tip_engine")         # oček.: discover(filters?) -> list[dict]
flamengo_strategy= _safe_import("flamengo_strategy")  # oček.: score(match_dict) -> procenta nebo 0–1
tipsport_check   = _safe_import("tipsport_check")     # oček.: verify_odds({match,market,pick,min_odds}) -> {"ok":True,"odds":1.63}
sources_files    = _safe_import("sources_files")      # volitelný loader z tvých souborů

# ---------------- DATOVÝ MODEL ----------------
@dataclass
class Tip:
    dt: datetime
    liga: str
    zapas: str
    trh: str
    pick: str
    kurz: float
    conf: float
    source: str = "engine"

    def to_text(self) -> str:
        t = self.dt.strftime("%d.%m. %H:%M")
        return (
            f"🕒 {t}  •  {self.liga}\n"
            f"⚽ {self.zapas}\n"
            f"🎯 {self.trh}: *{self.pick}*  @ {self.kurz:.2f}\n"
            f"💡 Důvěra: *{round(self.conf)}%*\n"
            f"— — —"
        )

    @staticmethod
    def _auto_dt(obj: Dict[str, Any]) -> datetime:
        for k in ("dt", "time", "kickoff", "start"):
            if k in obj:
                v = obj[k]
                if isinstance(v, (int, float)):  # unix
                    return datetime.fromtimestamp(v, timezone.utc)
                if isinstance(v, str):
                    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
                                "%d.%m.%Y %H:%M", "%d.%m. %H:%M", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            d = datetime.strptime(v.strip(), fmt)
                            if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
                            return d
                        except: pass
        return datetime.now(timezone.utc) + timedelta(hours=2)

    @classmethod
    def from_any(cls, obj: Dict[str, Any]) -> "Tip":
        liga = obj.get("league") or obj.get("liga") or obj.get("competition") or "N/A"
        home = obj.get("home") or obj.get("team_home") or obj.get("homeTeam") or obj.get("home_name") or ""
        away = obj.get("away") or obj.get("team_away") or obj.get("awayTeam") or obj.get("away_name") or ""
        zapas = obj.get("match") or obj.get("zapas") or f"{home} vs {away}".strip()
        trh  = obj.get("market") or obj.get("trh") or obj.get("bet_type") or "Trh"
        pick = obj.get("pick") or obj.get("selection") or obj.get("value") or "?"
        kurz = obj.get("odds") or obj.get("kurz") or 1.50
        try: kurz = float(kurz)
        except: kurz = 1.50
        conf = obj.get("conf") or obj.get("confidence") or obj.get("prob") or 80
        try:
            conf = float(conf)
            if conf <= 1: conf *= 100.0
        except: conf = 80.0
        dt = cls._auto_dt(obj)
        source = obj.get("source") or "engine"
        return cls(dt=dt, liga=liga, zapas=zapas, trh=trh, pick=pick, kurz=kurz, conf=conf, source=source)

# ---------------- STORE ----------------
class TipStore:
    def __init__(self): self.tips: List[Tip] = []
    def set(self, tips: List[Tip]): self.tips = sorted(tips, key=lambda x: x.dt)
    def clear(self): self.tips = []
    def all(self) -> List[Tip]: return list(self.tips)

STORE = TipStore()

# ---------------- UTIL ----------------
def ensure_tz(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def unique_by_market(tips: List[Tip], limit: int) -> List[Tip]:
    seen, out = set(), []
    for t in tips:
        key = t.trh.strip().lower()
        if key in seen: continue
        seen.add(key); out.append(t)
        if len(out) >= limit: break
    if len(out) < limit:
        for t in tips:
            if t not in out:
                out.append(t)
                if len(out) >= limit: break
    return out

def load_from_json_files() -> List[Tip]:
    cand: List[Tip] = []
    files = ["tipsport_today.json", "sofascore_today.json", "understat_today.json"]
    for fn in files:
        if not os.path.exists(fn): continue
        try:
            with open(fn, "r", encoding="utf-8") as f: data = json.load(f)
            items = data.get("items") or data.get("tips") or data.get("matches") if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for row in items:
                try: cand.append(Tip.from_any(row))
                except: pass
        except Exception as e:
            log.warning(f"Cannot load {fn}: {e}")
    return cand

# ---------------- PIPELINE (s filtry) ----------------
def run_pipeline(filters: Dict[str, Any] | None = None) -> List[Tip]:
    """
    filters:
      sport='fotbal'/'hokej'/..., liga='CZ1', minconf=85, live=0/1, window='3h', max=MAX_TIPS
    """
    filters = filters or {}
    want_sport = (filters.get("sport") or "").strip().lower()
    want_liga  = (filters.get("liga") or "").strip().lower()
    want_live  = bool(int(filters.get("live", 0)))
    window_str = (filters.get("window") or "").strip().lower()
    max_out    = int(filters.get("max", MAX_TIPS))
    local_min  = float(filters.get("minconf", MIN_CONF))

    now = datetime.now(timezone.utc)
    win_until: Optional[datetime] = None
    if window_str.endswith("h"):
        try: win_until = now + timedelta(hours=int(window_str[:-1]))
        except: pass

    candidates: List[Tip] = []

    # 1) Discovery
    try:
        if tip_engine and hasattr(tip_engine, "discover"):
            if "filters" in tip_engine.discover.__code__.co_varnames:
                rows = tip_engine.discover(filters=filters)
            else:
                rows = tip_engine.discover()
            for r in rows: candidates.append(Tip.from_any(r))
            log.info(f"tip_engine.discover -> {len(candidates)}")
        elif sources_files and hasattr(sources_files, "load_today"):
            rows = sources_files.load_today()
            for r in rows: candidates.append(Tip.from_any(r))
            log.info(f"sources_files.load_today -> {len(candidates)}")
    except Exception:
        log.warning("Discovery modules failed, fallback to JSON.")
        log.debug(traceback.format_exc())

    if not candidates:
        candidates = load_from_json_files()
        log.info(f"fallback JSON -> {len(candidates)}")

    # Hrubé filtry
    base: List[Tip] = []
    for t in candidates:
        if want_sport and (want_sport not in t.liga.lower() and want_sport not in t.zapas.lower()):
            continue
        if want_liga and want_liga not in t.liga.lower():
            continue
        if win_until and ensure_tz(t.dt) > win_until:
            continue
        # live flag – pokud zdroj neumí, necháme projít
        if want_live and t.source and "live" not in t.source.lower():
            pass
        base.append(t)
    candidates = base

    # 2) Analýza (Flamengo)
    try:
        if flamengo_strategy and hasattr(flamengo_strategy, "score"):
            for t in candidates:
                try:
                    score = flamengo_strategy.score({
                        "league": t.liga,
                        "match": t.zapas,
                        "market": t.trh,
                        "pick": t.pick,
                        "odds": t.kurz,
                        "dt": ensure_tz(t.dt).isoformat(),
                    })
                    if isinstance(score, (int, float)):
                        t.conf = score*100 if score <= 1 else score
                except: continue
            log.info("flamengo_strategy.score applied")
    except Exception:
        log.debug(traceback.format_exc())

    # 3) Tipsport ověření kurzů
    try:
        if tipsport_check and hasattr(tipsport_check, "verify_odds"):
            ok: List[Tip] = []
            for t in candidates:
                try:
                    res = tipsport_check.verify_odds({
                        "match": t.zapas, "market": t.trh, "pick": t.pick, "min_odds": t.kurz
                    })
                    if res and res.get("ok", True):
                        if "odds" in res: t.kurz = float(res["odds"])
                        ok.append(t)
                except: ok.append(t)
            candidates = ok
            log.info("tipsport_check.verify_odds applied")
    except Exception:
        log.debug(traceback.format_exc())

    # 4) Filtr důvěry + řazení + diverzita trhů
    candidates = [t for t in candidates if (t.conf or 0) >= local_min]
    candidates.sort(key=lambda x: (-(x.conf or 0), ensure_tz(x.dt)))
    candidates = unique_by_market(candidates, max_out)
    return candidates

# ---------------- TELEGRAM HANDLERY ----------------
async def start_cmd(u: Update, _):
    await u.message.reply_text(
        "Ahoj! 🟢 Jsem online.\n"
        "Napiš: /tip [N] [sport=...] [liga=...] [minconf=85] [live=0/1] [window=3h]\n"
        "Příklady:\n"
        "• /tip\n• /tip 3 sport=fotbal liga=CZ1 minconf=85\n• /tip 1 live=1 window=3h\n"
        "Další: /status, /reload, /cleartips, /help"
    )

async def help_cmd(u: Update, _):
    await u.message.reply_text(
        "/tip [N] [sport=...] [liga=...] [minconf=85] [live=0/1] [window=3h]\n"
        "/status – kontrola bota\n"
        "/reload – načti tipy ze souborů *_today.json (test)\n"
        "/cleartips – vyprázdni cache"
    )

async def status_cmd(u: Update, _):
    await u.message.reply_text("alive ✅")

async def reload_cmd(u: Update, _):
    tips = load_from_json_files()
    for t in tips:
        if not t.conf: t.conf = MIN_CONF
    tips = [t for t in tips if t.conf >= MIN_CONF]
    tips.sort(key=lambda x: (-(x.conf or 0), ensure_tz(x.dt)))
    tips = unique_by_market(tips, MAX_TIPS)
    STORE.set(tips)
    await u.message.reply_text(f"🔁 Načteno ze souborů: {len(tips)} tipů.")
    for t in tips:
        await u.message.reply_text(t.to_text(), parse_mode="Markdown")

async def cleartips_cmd(u: Update, _):
    STORE.clear()
    await u.message.reply_text("🧹 Cache tipů vymazána.")

async def tip_cmd(u: Update, _):
    """
    /tip [N] [sport=...] [liga=...] [minconf=85] [live=0/1] [window=3h]
    Příklady:
      /tip
      /tip 3 sport=fotbal liga=CZ1 minconf=85
      /tip 1 live=1 window=3h
    """
    text = (u.message.text or "").strip()
    parts = text.split()

    count = 1
    f: Dict[str, Any] = {"minconf": MIN_CONF, "max": MAX_TIPS}

    # 1) počet
    idx = 1
    if len(parts) > 1 and "=" not in parts[1]:
        try:
            count = max(1, min(10, int(parts[1])))
            idx = 2
        except:
            count = 1
            idx = 2

    # 2) klíč=hodnota
    for p in parts[idx:]:
        if "=" in p:
            k, v = p.split("=", 1)
            f[k.strip().lower()] = v.strip()

    if "minconf" in f:
        try: f["minconf"] = float(f["minconf"])
        except: f["minconf"] = MIN_CONF
    f["max"] = max(count, 1)

    await u.message.reply_text("🔎 Hledám zápasy… (analýza + kontrola Tipsport)")
    try:
        tips = run_pipeline(filters=f)
        if not tips:
            await u.message.reply_text("ℹ️ Nic nad prahem důvěry. Zkus upravit parametry (např. minconf/window).")
            return

        tips.sort(key=lambda x: -(x.conf or 0))
        picked = tips[:count]

        await u.message.reply_text(
            f"📊 Nalezeno {len(picked)} tip{'y' if len(picked)!=1 else ''} (min. důvěra {int(f['minconf'])}%)."
        )
        for t in picked:
            hodnoceni = "✅ Bezpečnější" if t.conf >= 90 else "⚠️ Vyšší riziko"
            msg = f"{t.to_text()}\n\n{hodnoceni}\nZdroj: {t.source or 'engine'}"
            await u.message.reply_text(msg, parse_mode="Markdown")

        STORE.set(picked)

    except Exception as e:
        log.error(f"/tip error: {e}")
        await u.message.reply_text("❌ Nepodařilo se dokončit vyhledání. Zkontroluj log na Renderu.")

async def echo_cmd(u: Update, _):
    if u.message and u.message.text and not u.message.text.startswith("/"):
        await u.message.reply_text("echo: " + u.message.text)

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(CommandHandler("cleartips", cleartips_cmd))
    app.add_handler(CommandHandler("tip", tip_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_cmd))

    log.info("RUNNING: polling mode (no webhook) | MIN_CONF=%.1f | MAX_TIPS=%d", MIN_CONF, MAX_TIPS)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
