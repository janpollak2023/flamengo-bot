# picks.py — Tipsport ONLY: Gól v 1. poločase (HT Over 0.5)
from __future__ import annotations
import os, re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Iterable, Set

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TZ = timezone(timedelta(hours=1))
TIMEOUT = (7, 14)

TIPS_URL_FOOT = os.getenv("TIPSPORT_URL_FOOT", "https://m.tipsport.cz/kurzy/fotbal-16")

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
    key: str = ""  # unikátní klíč pro anti-dup

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "cs-CZ,cs;q=0.9,en-US;q=0.8",
        "Cache-Control": "no-cache", "Pragma": "no-cache", "Referer": "https://www.google.com/",
    })
    retry = Retry(total=3, backoff_factor=0.6, status_forcelist=[429,500,502,503,504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

def _window_from_avg(minute: float) -> str:
    a = max(6, int(minute) - 8)
    b = min(44, int(minute) + 8)
    return f"{a}’–{b}’"

def _mk_key(name: str, ko: Optional[datetime]) -> str:
    return f"{name.lower()}|{ko.astimezone(TZ).strftime('%Y-%m-%d %H:%M') if ko else 'n/a'}"

# --- Tipsport rozpis (mobilní) – parsujeme řádky s časem a „ – “ mezi týmy ---
def _scrape_tipsport_list() -> List[Tip]:
    s = _session()
    try:
        r = s.get(TIPS_URL_FOOT, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        html = r.text
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    out: List[Tip] = []

    # V mobilním rozpisu bývá čas a název utkání v jedné větě/řádku
    # (držme se tolerantního regexu)
    candidates = soup.find_all(string=re.compile(r"\d{1,2}:\d{2}"))[:600]
    now = datetime.now(timezone.utc).astimezone(TZ)

    for node in candidates:
        line = node if isinstance(node, str) else node.get_text(" ", strip=True)
        if (" - " not in line) and (" – " not in line):
            continue

        tm = re.search(r"(\d{1,2}):(\d{2})", line)
        pair = re.search(r"([^\n\-–]+?)\s*[–-]\s*([^\n]+)", line)
        if not (tm and pair):
            continue

        hh, mm = int(tm.group(1)), int(tm.group(2))
        home, away = pair.group(1).strip(), pair.group(2).strip()
        # výkop dnes (pokud už po čase, posuň na zítra)
        ko = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if ko < now - timedelta(minutes=5):
            ko += timedelta(days=1)

        match = f"{home} – {away}"
        tip = Tip(
            match=match,
            league="Tipsport",
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            confidence=90,  # požadavek Honzy
            window=_window_from_avg(20.0),
            reason="Tipsport rozpis: trh HT Over 0.5 – priorita Flamengo.",
            odds=None,
            url=TIPS_URL_FOOT,
            kickoff=ko,
        )
        tip.key = _mk_key(tip.match, tip.kickoff)
        out.append(tip)

        if len(out) >= 120:
            break

    return out

def _filter_by_window(tips: List[Tip], start_offset_h: int, end_offset_h: int,
                      min_conf: int, exclude_keys: Set[str]) -> List[Tip]:
    now = datetime.now(timezone.utc).astimezone(TZ)
    start = now + timedelta(hours=max(0, start_offset_h))
    end = now + timedelta(hours=max(start_offset_h, end_offset_h))
    out: List[Tip] = []
    for t in tips:
        if t.kickoff and (start <= t.kickoff <= end) and t.confidence >= min_conf and t.key not in exclude_keys:
            out.append(t)
    # řazení: nejbližší výkop, pak abeceda
    out.sort(key=lambda x: (x.kickoff.timestamp() if x.kickoff else 1e15, x.match))
    return out

# === veřejná funkce pro main.py ===
def find_tipsport_ht_candidates(start_offset_h: int, end_offset_h: int,
                                min_conf: int = 90, exclude_keys: Set[str] | None = None,
                                limit: int = 6) -> List[Tip]:
    exclude = exclude_keys or set()
    all_rows = _scrape_tipsport_list()
    filt = _filter_by_window(all_rows, start_offset_h, end_offset_h, min_conf, exclude)
    return filt[:max(1, limit)]
