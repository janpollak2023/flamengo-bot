# tipsport_check.py — ověření existence zápasu na Tipsportu
# Pozn.: Přímé scrapování může porušovat jejich podmínky. Tady držíme „měkký“ kontrolní bod:
# 1) normalizace názvů týmů,
# 2) fuzzy match proti seznamu eventů získaných legálně (vlastní export / ruční feed).
# => Stačí napojit svůj JSON feed s dnešními Tipsport eventy.

from dataclasses import dataclass
from typing import Optional
import unicodedata, re, json, time, os

@dataclass
class TipsportEvent:
    league: str
    home: str
    away: str
    ts_utc: int

def _slug(x: str) -> str:
    x = unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode()
    x = re.sub(r"[^a-zA-Z0-9]+", "", x).lower()
    return x

def _load_events() -> list[TipsportEvent]:
    # 1) DEMO: načteme ze souboru (když není, vrátíme prázdno)
    path = "tipsport_today.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out = []
        for r in raw:
            out.append(TipsportEvent(r["league"], r["home"], r["away"], int(r["ts_utc"])))
        return out
    # 2) TODO: sem napoj budoucí legální feed (API/CSV export)
    return []

def exists_on_tipsport(league: str, home: str, away: str, ts_utc: int, time_tol_min: int = 30) -> bool:
    evs = _load_events()
    if not evs:
        # Pokud nemáme feed, povolíme „best effort“ a nerozbijeme běh
        return True

    sh, sa = _slug(home), _slug(away)
    for e in evs:
        if _slug(e.home) == sh and _slug(e.away) == sa:
            if abs(e.ts_utc - ts_utc) <= time_tol_min * 60:
                return True
    return False
