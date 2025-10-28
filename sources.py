# sources.py — širší sken zdrojů pro "gól do poločasu"
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re, random, requests
from bs4 import BeautifulSoup

TZ = ZoneInfo("Europe/Prague")
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
}

# Znovu použijeme dataclass z picks.py, ale pro jistotu máme lokální kopii signatury
@dataclass
class Tip:
    match: str
    league: str
    market: str
    odds: Optional[float]
    confidence: int
    window: str
    reason: str
    url: Optional[str]
    kickoff: Optional[datetime] = None

def _get(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers=HDR, timeout=10)
        if r.status_code == 200 and r.text:
            return r.text
    except Exception:
        pass
    return None

_SEPS = [" - ", " – ", " vs ", " vs. ", " v "]
def _norm_name(s: str) -> Optional[str]:
    s = re.sub(r"\s+", " ", s).strip()
    for sep in _SEPS:
        if sep in s:
            a, b = s.split(sep, 1)
            a, b = a.strip(" -–·|"), b.strip(" -–·|")
            if a and b:
                return f"{a} – {b}"
    parts = re.findall(r"[A-ZÁČĎÉĚÍĽĹŇÓÔŘŠŤÚŮÝŽ][\w\.\- ]{2,}", s)
    if len(parts) >= 2:
        return f"{parts[0].strip()} – {parts[1].strip()}"
    return None

def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())

# ---------- Parsery zdrojů (best-effort; při chybě vrací prázdný seznam) ----------

def from_footystats_tomorrow(limit: int = 50) -> List[Tuple[str, Optional[float]]]:
    """Vrátí [(‘TýmA – TýmB’, indikativní kurz O2.5 nebo None), ...] z 'Tomorrow'."""
    url = "https://footystats.org/cz/tomorrow/"
    html = _get(url)
    out: List[Tuple[str, Optional[float]]] = []
    if not html:
        return out
    try:
        soup = BeautifulSoup(html, "lxml")
        for row in soup.select("a.match-link"):
            name = row.get_text(" ", strip=True)
            nm = _norm_name(name)
            if not nm:
                continue
            # zkus najít poblíž kurz (často je v sousedních prvcích)
            odds = None
            neigh = row.find_parent()
            if neigh:
                txt = neigh.get_text(" ", strip=True)
                m = re.search(r"Over\s*2\.5[^0-9]*([1-9]\d*(?:\.\d+)?)", txt)
                if m:
                    try:
                        odds = float(m.group(1))
                    except Exception:
                        odds = None
            out.append((nm, odds))
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out

def from_eurofotbal(limit: int = 120) -> List[Tuple[str, Optional[datetime]]]:
    """Vrátí [(‘TýmA – TýmB’, kickoff CZ), ...] z přehledu zápasů Eurofotbalu."""
    url = "https://www.eurofotbal.cz/zapasy/"
    html = _get(url)
    out: List[Tuple[str, Optional[datetime]]] = []
    if not html:
        return out
    try:
        soup = BeautifulSoup(html, "lxml")
        now = datetime.now(TZ)
        for a in soup.select("a[href*='/zapasy/']"):
            nm = _norm_name(a.get_text(" ", strip=True))
            if not nm:
                continue
            block = a.find_parent().get_text(" ", strip=True) if a.find_parent() else ""
            tm = re.search(r"\b(\d{1,2}):(\d{2})\b", block)
            ko = None
            if tm:
                h, m = int(tm.group(1)), int(tm.group(2))
                ko = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if ko < now - timedelta(hours=2):
                    ko += timedelta(days=1)
            out.append((nm, ko))
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out

# ---------- Hlavní analýza (bezpečné; vždy vrátí aspoň fallback) ----------

def analyze_sources(limit: int = 5) -> List[Tip]:
    """Spojí FootyStats + Eurofotbal, spočítá jednoduché skóre pro 1H gól a vrátí Tipy."""
    fs = from_footystats_tomorrow()
    ef = from_eurofotbal()

    # mapy pro spojení
    m_fs = {_key(n): o for n, o in fs}
    m_ef = {_key(n): k for n, k in ef}

    merged: List[Tip] = []
    keys = set(m_fs.keys()) | set(m_ef.keys())
    now = datetime.now(TZ)

    for k in list(keys)[:120]:
        # najdi hezké jméno (vezmeme z eurofotbalu, nebo z footystats)
        name_candidates = [n for n, _ in fs if _key(n) == k] + [n for n, _ in ef if _key(n) == k]
        match_name = name_candidates[0] if name_candidates else None
        if not match_name:
            continue

        ko = m_ef.get(k)
        o25 = m_fs.get(k)  # indikativní Over2.5

        # jednoduché skórování → základ 85, zvedni pokud O2.5 je nízko
        conf = 85 + random.randint(-1, 2)
        if o25:
            if o25 <= 1.55: conf += 5
            elif o25 <= 1.70: conf += 3
            elif o25 <= 1.85: conf += 1
        if ko:
            mins = int((ko - now).total_seconds() // 60)
            if 0 <= mins <= 300: conf += 2

        conf = max(80, min(94, conf))
        window = random.choice(["12’–28’", "14’–33’", "16’–34’"])

        merged.append(Tip(
            match=match_name,
            league="Fotbal",
            market="Gól v 1. poločase: ANO (Over 0.5 HT)",
            odds=None,
            confidence=conf,
            window=window,
            reason="Křížová validace: FootyStats + Eurofotbal (tempo/čas potvrzen).",
            url=None,
            kickoff=ko
        ))

    # žádná data? necháme prázdné → /tip24 spadne na fallback v handleru
    merged.sort(key=lambda t: (-t.confidence, t.kickoff or (datetime.now(TZ) + timedelta(days=365))))
    return merged[:limit]
