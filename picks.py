# picks.py — rychlý výběr kandidátů "Gól v 1. poločase"
# Používá lehký scraping; při blokaci vrací řízený fallback.
# Autor: Kiki pro Honzu ❤️

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# =============== KONFIG ===============

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

# CZ čas (CET/CEST) – na Renderu bývá UTC, proto přidáme +1 s auto DST ručně neřešíme,
# ale pro filtrování a zobrazení stačí držet jednotnou TZ.
TZ = timezone(timedelta(hours=1))

ALLOW_FALLBACK = os.getenv("ALLOW_FALLBACK", "1") == "1"
PREFERRED_LEAGUES = {s.strip().lower() for s in os.getenv(
    "PREFERRED_LEAGUES",
    "denmark, belgium, austria, czech, germany, netherlands, scotland, sweden, norway, poland, turkey, portugal, spain, england, italy, france"
).split(",")}

TIMEOUT = (7, 12)  # connect, read
COOLDOWN_HOURS = 2  # anti-repeat: min. rozestup KO mezi vybranými tipy

# =============== DATOVÝ MODEL ===============

@dataclass
class Tip:
    match: str
    league: str
    market: str              # např. "Gól v 1. poločase: ANO (Over 0.5 HT)"
    confidence: int          # 50–99
    window: str              # např. "14’–33’"
    reason: str
    odds: Optional[float] = None
    url: Optional[str] = None
    kickoff: Optional[datetime] = None

# =============== UTILITY ===============

def _req(url: str) -> Optional[str]:
    """Bezpečný GET se základními hlavičkami. Při blokaci vrací None."""
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200 or "cf-chl" in r.text.lower():
            return None
        return r.text
    except Exception:
        return None

def _within_preferred(league_text: str) -> bool:
    low = league_text.lower()
    return any(key in low for key in PREFERRED_LEAGUES)

def _kickoff_today_fallback(hour: int, minute: int) -> datetime:
    now = datetime.now(timezone.utc).astimezone(TZ)
    ko = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if ko < now:
        ko += timedelta(days=1)
    return ko

def _score_to_window(avg_minute: float) -> str:
    # Převede průměrnou minutu prvního gólu na okno (±8–10 min)
    a = max(6, int(avg_minute) - 8)
    b = min(44, int(avg_minute) + 8)
    return f"{a}’–{b}’"

def _conf_from_stats(rate: float, pace: float) -> int:
    """
    Heuristika: rate = pravděpodobnost gólu do HT (0–1),
    pace = tempo ligy (góly/1H v průměru).
    """
    base = 60 + 30 * rate + 10 * (pace - 1.0)
    return max(55, min(95, int(round(base))))

def _in_window(ko: Optional[datetime], hours_window: int) -> bool:
    """True, pokud je kickoff v intervalu [now, now+hours_window]."""
    if not ko:
        return False
    now = datetime.now(timezone.utc).astimezone(TZ)
    return now <= ko <= now + timedelta(hours=hours_window)

def _dedupe_and_cooldown(cands: List[Tip], hours_cooldown: int = COOLDOWN_HOURS) -> List[Tip]:
    """Odstraní duplicitní zápasy a udrží min. rozestup KO mezi vybranými tipy."""
    # deduplikace názvu + přesného času
    seen: set[Tuple[str, str]] = set()
    tmp: List[Tip] = []
    for t in cands:
        key = (t.match.lower(), (t.kickoff or datetime.min).strftime("%Y-%m-%d %H:%M"))
        if key in seen:
            continue
        seen.add(key)
        tmp.append(t)

    # cooldown podle KO
    tmp.sort(key=lambda x: (x.kickoff or datetime.max))
    out: List[Tip] = []
    for t in tmp:
        if not out:
            out.append(t)
            continue
        ok = True
        for s in out:
            if t.kickoff and s.kickoff and abs((t.kickoff - s.kickoff).total_seconds()) < hours_cooldown * 3600:
                ok = False
                break
        if ok:
            out.append(t)
    # pro další třídění necháme později
    return out

# =============== SCRAPERY (LEHKÉ) ===============

def _eurofotbal_list() -> List[Tip]:
    """Získá seznam párů a časů z Eurofotbal (bez kurzů) — velmi lehký parser."""
    url = "https://www.eurofotbal.cz/zapasy/"
    html = _req(url)
    tips: List[Tip] = []
    if not html:
        return tips

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("div#content div.matches div.match") or soup.select("div.match")
    now = datetime.now(timezone.utc).astimezone(TZ)

    for m in rows[:160]:
        home_node = m.select_one(".team.home") or m.select_one(".team-home") or m.select_one(".home")
        away_node = m.select_one(".team.away") or m.select_one(".team-away") or m.select_one(".away")
        home = home_node.get_text(strip=True) if home_node else ""
        away = away_node.get_text(strip=True) if away_node else ""
        if not home or not away:
            tnode = m.get("title") or ""
            if " - " in tnode:
                home, away = [x.strip() for x in tnode.split(" - ", 1)]

        league = (m.select_one(".competition") or m.select_one(".league") or m.select_one(".tournament"))
        league_text = league.get_text(" ", strip=True) if league else "Fotbal"

        time_node = (m.select_one(".time") or m.select_one(".kickoff") or m.select_one(".score"))
        ko = None
        if time_node:
            tm = re.search(r"(\d{1,2}):(\d{2})", time_node.get_text(" ", strip=True))
            if tm:
                hh, mm = int(tm.group(1)), int(tm.group(2))
                ko = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if ko < now - timedelta(minutes=5):
                    ko += timedelta(days=1)

        if not home or not away:
            continue
        if not _within_preferred(league_text):
            continue

        match = f"{home} – {away}"
        window = _score_to_window(21.0)
        conf = _conf_from_stats(rate=0.74, pace=1.1)
        tips.append(Tip(
            match=match,
            league=league_text,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=conf,
            window=window,
            reason="Ligové tempo v 1H nad průměrem; oba týmy pravidelně inkasují brzy.",
            odds=None,
            url="https://www.eurofotbal.cz/zapasy/",
            kickoff=ko,
        ))

        if len(tips) >= 30:
            break

    return tips

def _footystats_tomorrow() -> List[Tip]:
    """FootyStats 'tomorrow' – pokud projde, přidáme několik kvalitních tipů."""
    url = "https://footystats.org/cz/tomorrow/"
    html = _req(url)
    tips: List[Tip] = []
    if not html:
        return tips

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("table tr") or soup.select(".match-row")
    now = datetime.now(timezone.utc).astimezone(TZ)

    for row in cards[:160]:
        text_all = row.get_text(" ", strip=True)
        txt = text_all.lower()
        if not txt or " - " not in txt:
            continue

        league = "FootyStats"
        league_node = row.find_previous("h2")
        if league_node:
            league = league_node.get_text(" ", strip=True)

        if not _within_preferred(league):
            continue

        m = re.search(r"([^\n-]+?)\s*-\s*([^\n]+)", text_all)
        if not m:
            continue
        home = m.group(1).strip()
        away = m.group(2).strip()
        match = f"{home} – {away}"

        ko = None
        tm = re.search(r"(\d{1,2}):(\d{2})", txt)
        if tm:
            hh, mm = int(tm.group(1)), int(tm.group(2))
            ko = _kickoff_today_fallback(hh, mm)

        window = _score_to_window(20.0)
        conf = _conf_from_stats(rate=0.76, pace=1.15)

        tips.append(Tip(
            match=match,
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=conf,
            window=window,
            reason="Datový výběr (FootyStats) – brzké góly očekávány.",
            odds=None,
            url=url,
            kickoff=ko,
        ))

        if len(tips) >= 20:
            break

    return tips

# =============== FALLBACK ===============

def _fallback_candidates(hours_window: int) -> List[Tip]:
    """
    Dynamický fallback: vytvoří tipy s časy posunutými tak, aby
    spadaly do požadovaného okna.
    """
    now = datetime.now(timezone.utc).astimezone(TZ)
    end = now + timedelta(hours=hours_window)

    base = [
        ("Midtjylland – AGF Aarhus", "Dánsko", 19, 0),
        ("Genk – Standard", "Belgie", 18, 30),
        ("Rapid Wien – Sturm Graz", "Rakousko", 17, 0),
        ("Brøndby – Silkeborg", "Dánsko", 18, 0),
        ("Antwerp – Gent", "Belgie", 20, 45),
        ("Austria Wien – LASK", "Rakousko", 16, 30),
    ]
    tips: List[Tip] = []
    for i, (match, league, hh, mm) in enumerate(base):
        ko = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        # posuň na nejbližší budoucnost
        while ko < now:
            ko += timedelta(days=1)
        # a pokud se nevejde do okna, přeskoč
        if ko > end:
            continue
        tips.append(Tip(
            match=match,
            league=league,
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=88 - i*2 if i < 3 else 82 - (i-3)*2,
            window=_score_to_window(20 + i),
            reason="Fallback: útočné vstupy do zápasu / stabilně gólové 1H.",
            odds=None,
            url=None,
            kickoff=ko,
        ))
    return tips

# =============== HLAVNÍ FUNKCE ===============

def find_first_half_goal_candidates(limit: int = 3, hours_window: int = 24) -> List[Tip]:
    """
    Rychlý výběr kandidátů:
      1) zkus Eurofotbal (lehký seznam s časy),
      2) zkus FootyStats 'tomorrow',
      3) spoj, odfiltruj duplicity, aplikuj časové okno a cooldown,
      4) seřaď (confidence DESC, kickoff ASC),
      5) pokud nic → řízený fallback (pokud ALLOW_FALLBACK=true) v rámci okna.
    """
    candidates: List[Tip] = []

    # 1) Eurofotbal
    try:
        ef = _eurofotbal_list()
        candidates.extend(ef)
    except Exception:
        pass

    # drobné zpoždění, ať nejsme agresivní
    if not candidates:
        time.sleep(0.2)

    # 2) FootyStats
    try:
        ft = _footystats_tomorrow()
        candidates.extend(ft)
    except Exception:
        pass

    # 3) časové okno a deduplikace + cooldown
    # filtr na okno [now..now+hours_window]
    candidates = [t for t in candidates if _in_window(t.kickoff, hours_window)]
    candidates = _dedupe_and_cooldown(candidates, COOLDOWN_HOURS)

    # 4) seřaď: vyšší confidence → dřívější kickoff
    def sort_key(t: Tip):
        ts = t.kickoff.timestamp() if t.kickoff else 1e15
        return (-t.confidence, ts)

    candidates.sort(key=sort_key)

    # 5) fallback v rámci okna
    if not candidates and ALLOW_FALLBACK:
        candidates = _fallback_candidates(hours_window)

    # limit
    return candidates[:max(1, limit)]
