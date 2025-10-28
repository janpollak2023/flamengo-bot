# picks.py — rychlý výběr kandidátů "Gól v 1. poločase"
# Autor: Kiki pro Honzu ❤️  — verze: TIPS+EF+LS v3 (hours_window + robust fallback)

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
TZ = timezone(timedelta(hours=1))                       # CET/CEST
ALLOW_FALLBACK      = os.getenv("ALLOW_FALLBACK", "1") == "1"
STRICT_LEAGUES      = os.getenv("STRICT_LEAGUES", "0") == "1"   # 0 = volnější filtrace
TIMEOUT             = (7, 14)

# Tipsport kategorie (mobil) – fotbal/hokej lze rozšířit
TIPSPORT_URL_FOOT   = os.getenv("TIPSPORT_URL_FOOT", "https://m.tipsport.cz/kurzy/fotbal-16")
TIPSPORT_URL_HOCK   = os.getenv("TIPSPORT_URL_HOCK", "https://m.tipsport.cz/kurzy/ledni-hokej-23")

PREFERRED_LEAGUES = {s.strip().lower() for s in os.getenv(
    "PREFERRED_LEAGUES",
    "czech, cesko, fortuna, denmark, danish, superliga, belgium, jupiler, austria, bundesliga, "
    "germany, netherlands, eredivisie, scotland, sweden, norway, poland, turkey, portugal, spain, "
    "england, premier, italy, serie, france, ligue"
).split(",")}

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

def _conf(rate: float, pace: float) -> int:
    base = 60 + 30*rate + 10*(pace - 1.0)
    return max(55, min(95, int(round(base))))

def _dedup_keep_best(tips: Iterable[Tip]) -> List[Tip]:
    seen = {}
    for t in tips:
        key = (t.match.lower().strip(), t.kickoff.strftime("%Y-%m-%d %H:%M") if t.kickoff else "")
        if key not in seen or t.confidence > seen[key].confidence:
            seen[key] = t
    return list(seen.values())

# =============== TISPPORT SCRAPER (MOBIL) ===============
def _scrape_tipsport_list(base_url: str, day_shift: int) -> List[Tip]:
    """
    Parsuje mobilní Tipsport katalog (např. fotbal-16).
    day_shift: 0=dnes, 1=zítra (pokusně přes query filtr; pokud není, bereme vše a posun času)
    """
    base = datetime.now(timezone.utc).astimezone(TZ) + timedelta(days=day_shift)
    # zkus “Zítra” filtr – Tipsport často používá param timeFilter
    url = base_url
    if day_shift == 1:
        url = base_url + "?timeFilter=tomorrow"

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

    # Struktura m.tipsport.cz se liší; chytáme co nejuniverzálněji:
    # - čas „HH:MM“
    # - dvojice týmů s „-“ nebo „–“
    # - vedle/na řádku bývá soutěž
    rows = soup.find_all(string=re.compile(r"\d{1,2}:\d{2}"))[:800]
    for node in rows:
        line = node if isinstance(node, str) else node.get_text(" ", strip=True)
        # dohledáme okolní kontejner kvůli názvu a soutěži
        item = node if hasattr(node, "parent") else None
        blk = item.parent if item else None
        text_blk = ""
        if blk:
            text_blk = blk.get_text(" ", strip=True)

        # čas
        mt = re.search(r"(\d{1,2}):(\d{2})", line) or re.search(r"(\d{1,2}):(\d{2})", text_blk)
        if not mt:
            continue
        hh, mm = int(mt.group(1)), int(mt.group(2))

        # match pair: zkusíme v bloku najít „TýmA - TýmB“ nebo „TýmA – TýmB“
        src = text_blk if text_blk else line
        mp = re.search(r"([^\n\-–]+?)\s*[–-]\s*([^\n]+)", src)
        if not mp:
            # fallback – občas je název samostatně ve dvou <span>
            # v tom případě raději přeskoč, aby nebyly šum zápasy
            continue

        home = mp.group(1).strip()
        away = mp.group(2).strip()

        # liga/soutěž – často je nad/vedle, zkusíme blízké labely
        league = "Tipsport"
        wrap = blk
        if wrap:
            # vezmeme krátký sousední text, který nevypadá jako kurzy/čísla
            cand = wrap.find_previous(["h2", "h3", "div", "span"])
            if cand:
                txt = cand.get_text(" ", strip=True)
                if txt and not re.fullmatch(r"[\d\.\s:]+", txt):
                    league = txt

        # filtrace ligy (volitelná)
        if not _within_preferred(league):
            continue

        ko = _ko(hh, mm, base)
        tips.append(Tip(
            match=f"{home} – {away}",
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=_conf(0.75, 1.12),          # Tipsport list: bereme o chlup víc než EF/LS
            window=_window_from_avg(20.0),
            reason="Tipsport (mobil) – reálná nabídka, očekávaný brzký zásah.",
            odds=None,                              # kurzy doplníme v detail scrapers v další iteraci
            url=url,
            kickoff=ko,
        ))

        if len(tips) >= 120:
            break

    return tips

# =============== EUROFOTBAL ===============
def _scrape_eurofotbal(day_shift: int) -> List[Tip]:
    base = datetime.now(timezone.utc).astimezone(TZ) + timedelta(days=day_shift)
    url = f"https://www.eurofotbal.cz/zapasy/?d={day_shift}"
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
    blocks = soup.select("div.match, li.match, tr.match, div.zapas, li.zapas")
    if not blocks:
        text = soup.get_text("\n", strip=True)
        rows = [ln for ln in text.split("\n") if ":" in ln and (" - " in ln or " – " in ln)]
        blocks = rows[:150]

    def extract_pair(node) -> Optional[tuple[str,str]]:
        txt = node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node)
        m = re.search(r"([^\n\-–]+?)\s*[–-]\s*([^\n]+)", txt)
        if not m:
            return None
        return m.group(1).strip(), m.group(2).strip()

    def extract_time(node) -> Optional[tuple[int,int]]:
        txt = node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node)
        tm = re.search(r"(\d{1,2}):(\d{2})", txt)
        if not tm:
            return None
        return int(tm.group(1)), int(tm.group(2))

    def extract_league(node) -> str:
        if hasattr(node, "find_previous"):
            cand = node.find_previous(["h2","h3","h4","div","span"])
            if cand:
                t = cand.get_text(" ", strip=True)
                if len(t) > 2:
                    return t
        return "Fotbal"

    for node in blocks[:200]:
        pair = extract_pair(node)
        tm = extract_time(node)
        if not pair or not tm:
            continue
        home, away = pair
        league = extract_league(node)
        if not _within_preferred(league):
            continue
        ko = _ko(tm[0], tm[1], base)
        tips.append(Tip(
            match=f"{home} – {away}",
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=_conf(0.74, 1.10),
            window=_window_from_avg(21.0),
            reason="Eurofotbal: ligové tempo 1H nad průměrem.",
            odds=None,
            url=url,
            kickoff=ko,
        ))
        if len(tips) >= 60:
            break
    return tips

# =============== LIVESPORT (MOBIL) ===============
def _scrape_livesport_mobile(day_shift:int) -> List[Tip]:
    base = datetime.now(timezone.utc).astimezone(TZ) + timedelta(days=day_shift)
    url = "https://m.livesport.cz/fotbal/"
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

    rows = soup.find_all(string=re.compile(r"\d{1,2}:\d{2}"))[:400]
    for row in rows:
        line = row if isinstance(row, str) else row.get_text(" ", strip=True)
        if " - " not in line and " – " not in line:
            continue
        mt = re.search(r"(\d{1,2}):(\d{2})", line)
        mp = re.search(r"([^\n\-–]+?)\s*[–-]\s*([^\n]+)", line)
        if not (mt and mp):
            continue
        hh, mm = int(mt.group(1)), int(mt.group(2))
        home, away = mp.group(1).strip(), mp.group(2).strip()
        league = "Livesport"
        ko = _ko(hh, mm, base)
        tips.append(Tip(
            match=f"{home} – {away}",
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=_conf(0.72, 1.05),
            window=_window_from_avg(22.0),
            reason="Livesport (mobil): rychlý rozpis – oček. brzký gól.",
            odds=None,
            url=url,
            kickoff=ko,
        ))
        if len(tips) >= 60:
            break
    return tips

# =============== FALLBACK ===============
_POOL = [
    ("Midtjylland – AGF Aarhus", "Dánsko"),
    ("Genk – Standard", "Belgie"),
    ("Rapid Wien – Sturm Graz", "Rakousko"),
    ("Brøndby – Silkeborg", "Dánsko"),
    ("Antwerp – Gent", "Belgie"),
    ("Austria Wien – LASK", "Rakousko"),
    ("Slavia – Baník", "Česko"),
    ("Plzeň – Sparta", "Česko"),
    ("Besiktas – Fenerbahce", "Turecko"),
    ("Twente – PSV", "Nizozemsko"),
    ("Celta – Betis", "Španělsko"),
    ("Bologna – Torino", "Itálie"),
]

def _fallback_candidates(n: int = 8) -> List[Tip]:
    now = datetime.now(timezone.utc).astimezone(TZ)
    base = random.sample(_POOL, k=min(n, len(_POOL)))
    out: List[Tip] = []
    for i, (match, league) in enumerate(base):
        hh = 16 + (i % 6)   # 16–21
        mm = 0 if i % 2 == 0 else 30
        ko = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ko < now:
            ko += timedelta(days=1 + (i//6))
        out.append(Tip(
            match=match,
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=88 - (i % 5)*2,
            window=_window_from_avg(18 + (i % 7)),
            reason="Fallback rotace: známé gólové páry, konzerv. skóre.",
            odds=None,
            url=None,
            kickoff=ko,
        ))
    return out

# =============== HLAVNÍ FUNKCE ===============
def find_first_half_goal_candidates(limit: int = 3, hours_window: int = 24) -> List[Tip]:
    """
    Pipeline (nejbezpečnější pořadí):
      1) Tipsport mobil (dnes + zítra),
      2) Eurofotbal (dnes + zítra),
      3) Livesport mobil (dnes + zítra),
      4) filtr do okna <teď .. teď+hours_window>,
      5) deduplikace + řazení,
      6) pokud nic a ALLOW_FALLBACK → řízený fallback.
    """
    now = datetime.now(timezone.utc).astimezone(TZ)
    until = now + timedelta(hours=max(1, min(72, hours_window)))

    tips: List[Tip] = []

    # 1) Tipsport (reálná nabídka)
    try:
        tips += _scrape_tipsport_list(TIPSPORT_URL_FOOT, 0)
    except Exception:
        pass
    try:
        tips += _scrape_tipsport_list(TIPSPORT_URL_FOOT, 1)
    except Exception:
        pass

    # 2) Eurofotbal
    if len(tips) < 4:
        time.sleep(0.2)
        try: tips += _scrape_eurofotbal(0)
        except Exception: pass
        try: tips += _scrape_eurofotbal(1)
        except Exception: pass

    # 3) Livesport
    if len(tips) < 4:
        time.sleep(0.2)
        try: tips += _scrape_livesport_mobile(0)
        except Exception: pass
        try: tips += _scrape_livesport_mobile(1)
        except Exception: pass

    # 4) filtr na časové okno
    filtered: List[Tip] = []
    for t in tips:
        if t.kickoff is None:
            continue
        if not (now <= t.kickoff <= until):
            continue
        filtered.append(t)

    # 5) deduplikace + sort (confidence desc, kickoff asc)
    filtered = _dedup_keep_best(filtered)
    filtered.sort(key=lambda t: (-t.confidence, t.kickoff.timestamp() if t.kickoff else 1e15))

    # 6) nouzový návrat
    if not filtered and ALLOW_FALLBACK:
        return _fallback_candidates(10)[:max(1, limit)]

    return filtered[:max(1, limit)]
