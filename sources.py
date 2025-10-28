# sources.py — rozšířený sken zápasů pro Flamengo /tip24
# Autor: Kiki pro Honzu ❤️

import re
import time
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Optional

TZ = timezone(timedelta(hours=1))  # SEČ/CEST

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


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

TIMEOUT = (7, 12)


# ==========================
#   HELPERY
# ==========================

def _req(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if r.status_code != 200 or "cf-chl" in r.text.lower():
            return None
        return r.text
    except Exception:
        return None


def _score_to_window(avg: float) -> str:
    a = max(6, int(avg) - 8)
    b = min(44, int(avg) + 8)
    return f"{a}’–{b}’"


def _conf(rate: float) -> int:
    return max(70, min(95, int(rate * 100)))


def _kickoff(hour: int, minute: int) -> datetime:
    now = datetime.now(timezone.utc).astimezone(TZ)
    ko = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if ko < now - timedelta(minutes=10):
        ko += timedelta(days=1)
    return ko


# ==========================
#   SCRAPERY
# ==========================

def eurofotbal_scan() -> List[Tip]:
    url = "https://www.eurofotbal.cz/zapasy/"
    html = _req(url)
    tips: List[Tip] = []
    if not html:
        return tips

    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("div#content div.match")
    now = datetime.now(timezone.utc).astimezone(TZ)

    for b in blocks[:100]:
        home = b.select_one(".team.home, .team-home")
        away = b.select_one(".team.away, .team-away")
        time_node = b.select_one(".time")

        if not home or not away or not time_node:
            continue

        h, a = home.get_text(strip=True), away.get_text(strip=True)
        match = f"{h} – {a}"

        tm = re.search(r"(\d{1,2}):(\d{2})", time_node.get_text())
        ko = _kickoff(int(tm.group(1)), int(tm.group(2))) if tm else now

        league = b.get("data-competition", "Fotbal")
        tips.append(
            Tip(
                match=match,
                league=league,
                market="Gól v 1. poločase: ANO (Over 0.5 HT)",
                confidence=85,
                window=_score_to_window(21),
                reason="Eurofotbal.cz – ligový zápas, očekávané brzké góly.",
                odds=None,
                url=url,
                kickoff=ko,
            )
        )

    return tips


def footystats_scan() -> List[Tip]:
    url = "https://footystats.org/cz/tomorrow/"
    html = _req(url)
    tips: List[Tip] = []
    if not html:
        return tips

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tr") or soup.select(".match-row")

    for r in rows[:80]:
        text = r.get_text(" ", strip=True)
        if " - " not in text:
            continue
        m = re.search(r"([^\n-]+?)\s*-\s*([^\n]+)", text)
        if not m:
            continue
        home, away = m.group(1).strip(), m.group(2).strip()
        match = f"{home} – {away}"

        tm = re.search(r"(\d{1,2}):(\d{2})", text)
        ko = _kickoff(int(tm.group(1)), int(tm.group(2))) if tm else None

        tips.append(
            Tip(
                match=match,
                league="FootyStats",
                market="Gól v 1. poločase: ANO (Over 0.5 HT)",
                confidence=83,
                window=_score_to_window(20),
                reason="FootyStats.org – statisticky gólové týmy v 1H.",
                odds=None,
                url=url,
                kickoff=ko,
            )
        )

    return tips


# ==========================
#   HLAVNÍ FUNKCE
# ==========================

def analyze_sources(limit: int = 5) -> List[Tip]:
    """
    Získá seznam zápasů z různých webů a spojí je.
    """
    all_tips: List[Tip] = []

    try:
        ef = eurofotbal_scan()
        all_tips.extend(ef)
    except Exception:
        pass

    time.sleep(0.3)

    try:
        fs = footystats_scan()
        all_tips.extend(fs)
    except Exception:
        pass

    # seřadit podle confidence
    all_tips.sort(key=lambda t: (-t.confidence, t.kickoff or datetime.max))
    return all_tips[:limit]
