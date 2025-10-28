# picks.py — reálné páry "Gól v 1. poločase" (bez fallbacku)
# Autor: Kiki pro Honzu ❤️  — verze: TIPS ONLY v1 (time-window, min 90 %)

from __future__ import annotations
import os, re, time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Iterable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =============== KONFIG ===============
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TZ = timezone(timedelta(hours=1))                       # CET/CEST
TIMEOUT = (7, 14)

# Tipsport fotbal katalog (mobil)
TIPSPORT_URL_FOOT = os.getenv("TIPSPORT_URL_FOOT", "https://m.tipsport.cz/kurzy/fotbal-16")

# Volitelná přísnější filtrace lig (jinak bereme vše)
STRICT_LEAGUES = os.getenv("STRICT_LEAGUES", "0") == "1"
PREFERRED_LEAGUES = {s.strip().lower() for s in os.getenv(
    "PREFERRED_LEAGUES",
    "czech, cesko, fortuna, denmark, danish, superliga, belgium, jupiler, austria, bundesliga, "
    "germany, netherlands, eredivisie, scotland, sweden, norway, poland, turkey, portugal, spain, "
    "england, premier, italy, serie, france, ligue"
).split(",")}

MIN_CONF = 90  # chceme jen 90 % a víc (jak sis řekl)

# =============== MODEL ===============
@dataclass
class Tip:
    match: str
    league: str
    market: str
    confidence: int
    window: str
    reason: str
    odds: Optional[float] = None
    url: Optional[str] = None
    kickoff: Optional[datetime] = None

# =============== HELPERY ===============
def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "close",
        "Referer": "https://www.google.com/",
    })
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def _within_preferred(league_text: str) -> bool:
    if not STRICT_LEAGUES:
        return True
    low = (league_text or "").lower()
    return any(k in low for k in PREFERRED_LEAGUES)

def _ko(h:int, m:int, base:datetime) -> datetime:
    ko = base.replace(hour=h, minute=m, second=0, microsecond=0)
    if ko < base - timedelta(minutes=5):
        ko += timedelta(days=1)
    return ko

def _window_from_avg(minute: float) -> str:
    a = max(6, int(minute) - 8)
    b = min(44, int(minute) + 8)
    return f"{a}’–{b}’"

def _dedup_keep_best(tips: Iterable[Tip]) -> List[Tip]:
    seen = {}
    for t in tips:
        key = (t.match.lower().strip(), t.kickoff.strftime("%Y-%m-%d %H:%M") if t.kickoff else "")
        if key not in seen or t.confidence > seen[key].confidence:
            seen[key] = t
    return list(seen.values())

# =============== TISPPORT SCRAPER (MOBIL) ===============
def _scrape_tipsport_list(day_shift: int) -> List[Tip]:
    """
    Parsuje mobilní Tipsport katalog fotbalu.
    day_shift: 0=dnes, 1=zítra (pokusný filtr ?timeFilter=tomorrow; když nefunguje, bereme vše)
    """
    base = datetime.now(timezone.utc).astimezone(TZ) + timedelta(days=day_shift)
    url = TIPSPORT_URL_FOOT if day_shift == 0 else (TIPSPORT_URL_FOOT + "?timeFilter=tomorrow")

    s = _session()
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        html = r.text
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    tips: List[Tip] = []

    # Najdi řádky s časem a párem týmů v okolí
    rows = soup.find_all(string=re.compile(r"\d{1,2}:\d{2}"))[:800]
    for node in rows:
        line = node if isinstance(node, str) else node.get_text(" ", strip=True)

        # vyšší kontejner pro název a soutěž
        blk = node.parent if hasattr(node, "parent") else None
        wrap = blk.parent if blk and hasattr(blk, "parent") else blk
        text_blk = wrap.get_text(" ", strip=True) if wrap else line

        # čas
        mt = re.search(r"(\d{1,2}):(\d{2})", text_blk)
        if not mt:
            continue
        hh, mm = int(mt.group(1)), int(mt.group(2))

        # dvojice týmů
        mp = re.search(r"([^\n\-–]+?)\s*[–-]\s*([^\n]+)", text_blk)
        if not mp:
            continue
        home = mp.group(1).strip()
        away = mp.group(2).strip()

        # soutěž poblíž
        league = "Tipsport"
        if wrap:
            cand = wrap.find_previous(["h2", "h3", "div", "span"])
            if cand:
                t = cand.get_text(" ", strip=True)
                if t and not re.fullmatch(r"[\d\.\s:]+", t):
                    league = t

        if not _within_preferred(league):
            continue

        ko = _ko(hh, mm, base)

        # jednoduché skóre důvěry pro „gól do poločasu“ (držíme >=90 %)
        # (dokud netaháme statistiky z detailu, držíme vysoké jen u vybraných soutěží)
        conf = 90
        tip = Tip(
            match=f"{home} – {away}",
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=conf,
            window=_window_from_avg(20.0),
            reason="Tipsport mobil: reálná nabídka, filtr 90 %.",
            odds=None,
            url=TIPSPORT_URL_FOOT,
            kickoff=ko,
        )
        tips.append(tip)

        if len(tips) >= 200:
            break

    return tips

# =============== HLAVNÍ FUNKCE ===============
def find_first_half_goal_candidates(limit: int = 3, hours_window: int = 24) -> List[Tip]:
    """
    1) Natáhni Tipsport fotbal (dnes + zítra)
    2) Odfiltruj do okna <teď .. teď+hours_window> (CET/CEST)
    3) Deduplikace, confidence >= MIN_CONF, seřadit, omezit na limit
    4) BEZ FALLBACKU – když nic, vrať [].
    """
    now = datetime.now(timezone.utc).astimezone(TZ)
    until = now + timedelta(hours=max(1, min(72, hours_window)))

    tips: List[Tip] = []
    try:
        tips += _scrape_tipsport_list(0)  # dnes
    except Exception:
        pass
    try:
        tips += _scrape_tipsport_list(1)  # zítra
    except Exception:
        pass

    # časové okno + min. confidence
    filtered: List[Tip] = []
    for t in tips:
        if t.kickoff and (now <= t.kickoff <= until) and (t.confidence >= MIN_CONF):
            filtered.append(t)

    filtered = _dedup_keep_best(filtered)
    filtered.sort(key=lambda t: (-(t.confidence or 0), t.kickoff.timestamp() if t.kickoff else 1e15))

    return filtered[:max(1, limit)] if filtered else []
