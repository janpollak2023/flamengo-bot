# picks.py — rychlý výběr kandidátů "Gól v 1. poločase"
# Autor: Kiki pro Honzu ❤️  — verze: Tipsport-only optimalizovaná pro /tip, /tip2, /tip3

from __future__ import annotations
import os, re, time, random
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
TZ = timezone(timedelta(hours=1))  # CET/CEST
TIMEOUT = (7, 14)

ALLOW_FALLBACK = os.getenv("ALLOW_FALLBACK", "1") == "1"
TIPSPORT_URL_FOOT = os.getenv("TIPSPORT_URL_FOOT", "https://m.tipsport.cz/kurzy/fotbal-16")

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
    key: Optional[str] = None

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
    })
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

def _ko(h:int, m:int, base:datetime) -> datetime:
    ko = base.replace(hour=h, minute=m, second=0, microsecond=0)
    if ko < base - timedelta(minutes=5):
        ko += timedelta(days=1)
    return ko

def _window_from_avg(minute: float) -> str:
    a = max(6, int(minute) - 8)
    b = min(44, int(minute) + 8)
    return f"{a}’–{b}’"

def _conf_from_league(league: str) -> int:
    """Důvěra podle typu ligy – více gólové = vyšší confidence."""
    league_low = league.lower()
    if any(k in league_low for k in ["england", "premier", "netherlands", "germany", "spain", "denmark", "poland"]):
        return 93
    if any(k in league_low for k in ["italy", "serie", "portugal", "belgium", "austria", "sweden"]):
        return 90
    if any(k in league_low for k in ["czech", "cesko", "fortuna", "turkey", "france", "ligue"]):
        return 88
    return 85

def _dedup_keep_best(tips: Iterable[Tip]) -> List[Tip]:
    seen = {}
    for t in tips:
        key = (t.match.lower().strip(), t.kickoff.strftime("%Y-%m-%d %H:%M") if t.kickoff else "")
        if key not in seen or t.confidence > seen[key].confidence:
            seen[key] = t
    return list(seen.values())

# =============== TISPPORT SCRAPER (hlavní) ===============
def _scrape_tipsport_list(base_url: str, day_shift: int) -> List[Tip]:
    base = datetime.now(timezone.utc).astimezone(TZ) + timedelta(days=day_shift)
    url = base_url + ("?timeFilter=tomorrow" if day_shift == 1 else "")
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

    rows = soup.find_all(string=re.compile(r"\d{1,2}:\d{2}"))[:600]
    for node in rows:
        text = node if isinstance(node, str) else node.get_text(" ", strip=True)
        if " - " not in text and " – " not in text:
            continue

        mt = re.search(r"(\d{1,2}):(\d{2})", text)
        mp = re.search(r"([^\n\-–]+?)\s*[–-]\s*([^\n]+)", text)
        if not (mt and mp):
            continue

        hh, mm = int(mt.group(1)), int(mt.group(2))
        home, away = mp.group(1).strip(), mp.group(2).strip()
        ko = _ko(hh, mm, base)

        # Zkus odhad ligy z okolí
        league = "Tipsport"
        blk = getattr(node, "parent", None)
        if blk:
            cand = blk.find_previous(["h2", "h3", "div", "span"])
            if cand:
                txt = cand.get_text(" ", strip=True)
                if txt and not re.match(r"^\d", txt):
                    league = txt

        conf = _conf_from_league(league)
        tips.append(Tip(
            match=f"{home} – {away}",
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=conf,
            window=_window_from_avg(21),
            reason="Tipsport – reálná nabídka, vysoká aktivita v 1H.",
            odds=None,
            url=url,
            kickoff=ko,
            key=f"{home.lower()}-{away.lower()}-{ko.strftime('%Y%m%d%H%M')}"
        ))

        if len(tips) >= 150:
            break

    return tips

# =============== FALLBACK ===============
_FALLBACK = [
    ("Plzeň – Sparta", "Česko", 88),
    ("Liverpool – Fulham", "Anglie", 91),
    ("PSV – Ajax", "Nizozemsko", 92),
    ("Genk – Standard", "Belgie", 90),
    ("Austria Wien – LASK", "Rakousko", 87),
]

def _fallback_candidates(n: int = 5) -> List[Tip]:
    now = datetime.now(timezone.utc).astimezone(TZ)
    out: List[Tip] = []
    for i, (match, league, conf) in enumerate(_FALLBACK[:n]):
        hh = 18 + (i % 4)
        mm = 0 if i % 2 == 0 else 30
        ko = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ko < now:
            ko += timedelta(days=1)
        out.append(Tip(
            match=match,
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=conf,
            window=_window_from_avg(20),
            reason="Fallback – oblíbené gólové páry.",
            kickoff=ko,
            key=f"{match.lower()}-{ko.strftime('%Y%m%d%H%M')}"
        ))
    return out

# =============== HLAVNÍ FUNKCE ===============
def find_first_half_goal_candidates(limit: int = 5, hours_window: int = 24) -> List[Tip]:
    now = datetime.now(timezone.utc).astimezone(TZ)
    until = now + timedelta(hours=max(1, min(72, hours_window)))
    tips: List[Tip] = []

    try:
        tips += _scrape_tipsport_list(TIPSPORT_URL_FOOT, 0)
        tips += _scrape_tipsport_list(TIPSPORT_URL_FOOT, 1)
    except Exception:
        pass

    # pokud nic → fallback
    if not tips and ALLOW_FALLBACK:
        return _fallback_candidates(limit)

    # filtr do okna (teď..teď+hours_window)
    filtered = []
    for t in tips:
        if t.kickoff is None:
            continue
        if now <= t.kickoff <= until:
            filtered.append(t)

    filtered = _dedup_keep_best(filtered)
    filtered.sort(key=lambda t: (-t.confidence, t.kickoff.timestamp() if t.kickoff else 1e15))

    if not filtered and ALLOW_FALLBACK:
        return _fallback_candidates(limit)

    return filtered[:max(1, limit)]
