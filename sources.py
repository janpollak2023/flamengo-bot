# sources.py — rozšířený sken (Eurofotbal + FootyStats)
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
TIMEOUT = (7, 12)
TZ = timezone(timedelta(hours=1))  # CET/CEST

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

def _req(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        # Cloudflare / blokace
        if "cf-chl" in r.text.lower() or "attention required" in r.text.lower():
            return None
        return r.text
    except Exception:
        return None

# --- heuristiky pro skórování gólů do 1H ---
def _win(avg_first_goal_min: float) -> str:
    a = max(6, int(avg_first_goal_min) - 8)
    b = min(44, int(avg_first_goal_min) + 8)
    return f"{a}’–{b}’"

def _conf(rate: float, pace: float) -> int:
    base = 60 + 30 * rate + 10 * (pace - 1.0)
    return max(55, min(95, int(round(base))))

# ---------- EUROFOTBAL: dnešek + zítřek ----------
def _eurofotbal_list(days: int = 2) -> List[Tip]:
    url = "https://www.eurofotbal.cz/zapasy/"
    html = _req(url)
    out: List[Tip] = []
    if not html:
        return out

    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select("div#content div.matches") or [soup]

    now = datetime.now(timezone.utc).astimezone(TZ)
    today = now.date()

    for blk in blocks:
        # najdi hlavičku s datem (např. “Dnes”, “Zítra”, “Středa 29.10.”)
        heading = blk.find(["h2", "h3"])
        if heading:
            head = heading.get_text(" ", strip=True).lower()
        else:
            head = ""

        # rozhodni datum bloku
        if "zítra" in head or "zitra" in head:
            block_date = today + timedelta(days=1)
        elif "dnes" in head:
            block_date = today
        else:
            # zkus explicitní datum
            m = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.", head)
            if m:
                d, mth = int(m.group(1)), int(m.group(2))
                block_date = datetime(now.year, mth, d, tzinfo=TZ).date()
            else:
                block_date = today  # fallback

        if (block_date - today).days >= days:
            continue  # jen dnes/zítra

        rows = blk.select("div.match")
        for r in rows[:160]:
            home = (r.select_one(".team.home") or r.select_one(".home") or r.select_one(".team-home"))
            away = (r.select_one(".team.away") or r.select_one(".away") or r.select_one(".team-away"))
            home = home.get_text(strip=True) if home else ""
            away = away.get_text(strip=True) if away else ""

            # soutěž
            lg = (r.select_one(".competition") or r.select_one(".league") or r.select_one(".tournament"))
            league = lg.get_text(" ", strip=True) if lg else "Fotbal"

            # čas
            ko = None
            time_node = (r.select_one(".time") or r.select_one(".kickoff") or r.select_one(".score"))
            if time_node:
                tm = re.search(r"(\d{1,2}):(\d{2})", time_node.get_text(" ", strip=True))
                if tm:
                    hh, mm = int(tm.group(1)), int(tm.group(2))
                    ko = datetime(block_date.year, block_date.month, block_date.day,
                                  hh, mm, tzinfo=TZ)

            if not home or not away:
                continue

            match = f"{home} – {away}"
            out.append(Tip(
                match=match,
                league=league,
                market="Gól v 1. poločase: ANO (Over 0.5 HT)",
                confidence=_conf(0.74, 1.10),
                window=_win(20),
                reason="Eurofotbal (program) – vhodný profil na brzký gól.",
                odds=None,
                url="https://www.eurofotbal.cz/zapasy/",
                kickoff=ko,
            ))

    return out

# ---------- FOOTYSTATS: zítřek (tomorrow) ----------
def _footystats_tomorrow() -> List[Tip]:
    url = "https://footystats.org/cz/tomorrow/"
    html = _req(url)
    out: List[Tip] = []
    if not html:
        return out

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tr") or soup.select(".match-row")
    now = datetime.now(timezone.utc).astimezone(TZ)

    for row in rows[:160]:
        text = row.get_text(" ", strip=True)
        if " - " not in text:
            continue
        m = re.search(r"(.+?)\s*-\s*(.+)", text)
        if not m:
            continue
        home = m.group(1).strip()
        away = m.group(2).strip()

        tm = re.search(r"(\d{1,2}):(\d{2})", text)
        if tm:
            hh, mm = int(tm.group(1)), int(tm.group(2))
        else:
            hh, mm = 18, 0  # default

        # zítra
        z = (now + timedelta(days=1)).date()
        ko = datetime(z.year, z.month, z.day, hh, mm, tzinfo=TZ)

        out.append(Tip(
            match=f"{home} – {away}",
            league="FootyStats",
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=_conf(0.76, 1.15),
            window=_win(19),
            reason="FootyStats (tomorrow) – datový výběr na rychlý gól.",
            odds=None,
            url=url,
            kickoff=ko,
        ))
    return out

# ---------- PUBLIC ----------
def analyze_sources(limit: int = 5) -> List[Tip]:
    tips: List[Tip] = []
    try:
        tips.extend(_eurofotbal_list(days=2))   # dnes + zítra
    except Exception:
        pass
    try:
        tips.extend(_footystats_tomorrow())     # zítřek (datový doplněk)
    except Exception:
        pass

    # deduplikace + seřazení (dřívější výkop, vyšší confidence)
    uniq = {}
    for t in tips:
        key = (t.match.lower(), t.kickoff.isoformat() if t.kickoff else "")
        if key not in uniq:
            uniq[key] = t

    tips = list(uniq.values())
    tips.sort(key=lambda t: (t.kickoff.timestamp() if t.kickoff else 9e15, -t.confidence))
    return tips[:max(1, limit)]
