# flamengo_strategy.py — výpočet důvěry a návrh trhů podle „Flamengo“ zásad
from dataclasses import dataclass
from typing import Optional, Iterable
from markets import FOOTBALL_MARKETS

@dataclass
class MatchFacts:
    sport: str            # "football"
    league: str
    home: str
    away: str
    ts_utc: int           # start zápasu (unix)
    home_form10: Optional[float]  # 0..10 (posledních 10z)
    away_form10: Optional[float]
    xg_per90_sum: Optional[float] # součet xG/90 (oba týmy)
    pace_hint: Optional[float]    # tempo/pressing (volitelně)
    cards_avg: Optional[float]    # průměr karet /zápas
    corners_avg: Optional[float]  # průměr rohů /zápas
    injuries_abs: Optional[int]   # významnější absence
    notes: str = ""

@dataclass
class TipCandidate:
    market_code: str
    selection: str           # např. "Over 1.5", "ANO", "Domácí +0.25 AH"
    rationale: str
    confidence: int          # 0–100
    est_odds: Optional[float] = None

def clamp(x, lo=0, hi=100): return max(lo, min(hi, x))

def football_confidence(f: MatchFacts) -> int:
    base = 55
    if f.home_form10 is not None and f.away_form10 is not None:
        base += max(min((f.home_form10 - f.away_form10) * 1.5, 6), -6)
    if f.xg_per90_sum is not None:
        if f.xg_per90_sum >= 2.4: base += 12
        elif f.xg_per90_sum >= 2.1: base += 8
        elif f.xg_per90_sum >= 1.8: base += 4
        else: base -= 6
    if f.pace_hint and f.pace_hint >= 1.1:  # „rychlejší“ zápas
        base += 2
    if f.injuries_abs:                      # výrazné absence snižují jistotu
        base -= min(8, f.injuries_abs * 2)
    return int(clamp(base))

def propose_football_tips(f: MatchFacts) -> list[TipCandidate]:
    conf = football_confidence(f)
    tips: list[TipCandidate] = []

    # Bezpečí – góly (over) a HT gól
    if f.xg_per90_sum and f.xg_per90_sum >= 2.1:
        tips.append(TipCandidate("HT_GOAL_YES", "ANO",
                    "Vysoké xG → gól do poločasu často padá.", min(94, conf+6), 1.40))
        tips.append(TipCandidate("FT_OU_1_5", "Over 1.5",
                    "Oba týmy ofenzivní; chceme jistotu.", min(92, conf+4), 1.30))
    if f.xg_per90_sum and f.xg_per90_sum >= 1.9:
        tips.append(TipCandidate("FT_OU_2_5", "Over 2.5",
                    "Dost šancí → 3 góly reálné.", conf, 1.80))

    # BTTS
    if f.xg_per90_sum and f.xg_per90_sum >= 2.2:
        tips.append(TipCandidate("BTTS_YES", "ANO",
                    "Obě strany mají xG nad průměrem.", max(70, conf-5), 1.7))

    # Týmové overy favorita (jen lehce)
    if f.home_form10 and f.away_form10 and (f.home_form10 - f.away_form10) >= 2.5:
        tips.append(TipCandidate("HOME_OVER_1_5", "Domácí Over 1.5",
                    "Forma + domácí prostředí.", max(78, conf-2), 1.8))

    # Rohy a karty – podle průměrů
    if f.corners_avg and f.corners_avg >= 9.0:
        tips.append(TipCandidate("CORNERS_OVER", "Over (např. 9.5)",
                    "Zápas na rohy bohatý, trend potvrzuje průměr.", max(74, conf-6), 1.8))
    if f.cards_avg and f.cards_avg >= 4.8:
        tips.append(TipCandidate("CARDS_OVER", "Over (např. 4.5)",
                    "Tvrdší liga/soupeři, více faulů.", max(72, conf-8), 1.9))

    return tips
