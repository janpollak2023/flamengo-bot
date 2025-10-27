# markets.py – definice trhů a mapování na Tipsport
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
import re

@dataclass(frozen=True)
class MarketDef:
    code: str                 # interní kód
    label: str                # lidský popis (krátký)
    tipsport_name: str        # typický název na Tipsportu
    ts_patterns: List[re.Pattern]  # regexy pro fuzzy match
    group: Optional[str] = None    # např. "góly", "karty", …

    def matches_ts_text(self, text: str) -> bool:
        t = text.lower()
        return any(p.search(t) for p in self.ts_patterns)


# --- Pomůcky pro regex zkráceně
def P(*patterns: str) -> List[re.Pattern]:
    return [re.compile(p, re.I) for p in patterns]


# =========================
# FOTBAL – nejčastější trhy
# =========================
FOOTBALL_MARKETS: List[MarketDef] = [
    MarketDef(
        code="FT_OU_1_5",
        label="Počet gólů Over 1.5",
        tipsport_name="Počet gólů v zápase Over 1.5",
        ts_patterns=P(r"\b(over|více)\s*1[.,]?5\b", r"počet gólů.*over\s*1[.,]?5"),
        group="góly",
    ),
    MarketDef(
        code="FT_OU_2_5",
        label="Počet gólů Over 2.5",
        tipsport_name="Počet gólů v zápase Over 2.5",
        ts_patterns=P(r"\b(over|více)\s*2[.,]?5\b", r"počet gólů.*over\s*2[.,]?5"),
        group="góly",
    ),
    MarketDef(
        code="1H_GOAL_YES",
        label="Gól v 1. poločase – ANO",
        tipsport_name="Padne gól v 1. poločase – ANO",
        ts_patterns=P(r"(padne|bude).*(gól|gol).*(1\.\s*poločas|první poločas).*ano",
                       r"g[oó]l v 1\.? polo[cč]ase.*ano"),
        group="poločas",
    ),
    MarketDef(
        code="BTTS_YES",
        label="Oba týmy dají gól – ANO",
        tipsport_name="Oba týmy dají gól – ANO",
        ts_patterns=P(r"(oba.*(dají|da) g[oó]l).*ano", r"\bbtts\b.*(yes|ano)"),
        group="góly",
    ),
    MarketDef(
        code="HOME_OVER_1_5",
        label="Domácí góly Over 1.5",
        tipsport_name="Týmové góly domácí Over 1.5",
        ts_patterns=P(r"(dom[aá]c[ií]).*(g[oó]ly|g[oó]l[uů]).*over\s*1[.,]?5"),
        group="týmové góly",
    ),
    MarketDef(
        code="AWAY_OVER_1_5",
        label="Hosté góly Over 1.5",
        tipsport_name="Týmové góly hosté Over 1.5",
        ts_patterns=P(r"(host[eé]).*(g[oó]ly|g[oó]l[uů]).*over\s*1[.,]?5"),
        group="týmové góly",
    ),
    MarketDef(
        code="ASIAN_HOME_0",
        label="Asijský handicap 0 (DNB) – domácí",
        tipsport_name="Asijský handicap 0 (draw no bet) – domácí",
        ts_patterns=P(r"(asijsk[yý]|asian).*handicap.*0.*(dom[aá]c[ií]|home)",
                      r"(dnb|draw\s*no\s*bet).*(dom[aá]c[ií]|home)"),
        group="handicap",
    ),
    MarketDef(
        code="ASIAN_AWAY_0",
        label="Asijský handicap 0 (DNB) – hosté",
        tipsport_name="Asijský handicap 0 (draw no bet) – hosté",
        ts_patterns=P(r"(asijsk[yý]|asian).*handicap.*0.*(host[eé]|away)",
                      r"(dnb|draw\s*no\s*bet).*(host[eé]|away)"),
        group="handicap",
    ),
    MarketDef(
        code="ASIAN_HOME_+0_25",
        label="Asijský handicap +0.25 – domácí",
        tipsport_name="Asijský handicap +0.25 – domácí",
        ts_patterns=P(r"(asian|asijsk).*handicap.*\+?0[.,]?25.*(dom[aá]c[ií]|home)"),
        group="handicap",
    ),
    MarketDef(
        code="ASIAN_AWAY_+0_25",
        label="Asijský handicap +0.25 – hosté",
        tipsport_name="Asijský handicap +0.25 – hosté",
        ts_patterns=P(r"(asian|asijsk).*handicap.*\+?0[.,]?25.*(host[eé]|away)"),
        group="handicap",
    ),
    MarketDef(
        code="CARDS_OVER",
        label="Karty Over (celkem)",
        tipsport_name="Karty Over (celkem)",
        ts_patterns=P(r"karty?.*(over|více)"),
        group="karty",
    ),
    MarketDef(
        code="CORNERS_OVER",
        label="Rohy Over (celkem)",
        tipsport_name="Rohy Over (celkem)",
        ts_patterns=P(r"rohy?.*(over|více)"),
        group="rohy",
    ),
    MarketDef(
        code="1H_CORNERS_OVER",
        label="Rohy Over – 1. poločas",
        tipsport_name="Rohy Over – 1. poločas",
        ts_patterns=P(r"rohy?.*(1\.\s*poločas|prvn[íi]\s*poločas).*(over|více)"),
        group="rohy",
    ),
    MarketDef(
        code="1H_CARDS_OVER",
        label="Karty Over – 1. poločas",
        tipsport_name="Karty Over – 1. poločas",
        ts_patterns=P(r"karty?.*(1\.\s*poločas|prvn[íi]\s*poločas).*(over|více)"),
        group="karty",
    ),
]

# === Registry / helpery ===
MARKETS_BY_SPORT: Dict[str, List[MarketDef]] = {
    "fotbal": FOOTBALL_MARKETS,
    # budoucí: "hokej": HOCKEY_MARKETS, "tenis": TENNIS_MARKETS, …
}

# pro zpětnou kompatibilitu importů typu: from markets import FOOTBALL_MARKETS
__all__ = [
    "MarketDef",
    "FOOTBALL_MARKETS",
    "MARKETS_BY_SPORT",
    "get_market_by_code",
    "find_market",
]

def get_market_by_code(code: str, sport: str = "fotbal") -> Optional[MarketDef]:
    code = code.upper()
    for m in MARKETS_BY_SPORT.get(sport, []):
        if m.code == code:
            return m
    return None

def find_market(ts_text: str, sport: str = "fotbal") -> Optional[MarketDef]:
    """Najde nejlepší shodu podle Tipsport textu (název/varianta)."""
    for m in MARKETS_BY_SPORT.get(sport, []):
        if m.matches_ts_text(ts_text):
            return m
    # fallback: přesný začátek/obsah názvu
    t = ts_text.lower()
    for m in MARKETS_BY_SPORT.get(sport, []):
        if m.tipsport_name.lower() in t or m.label.lower() in t:
            return m
    return None
