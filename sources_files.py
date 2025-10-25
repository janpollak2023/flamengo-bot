# sources_files.py — „file-based“ zdroje, aby bot uměl číst víc zápasů hned
from typing import List
import json, os, time
from flamengo_strategy import MatchFacts

def _read_json(path: str):
    if not os.path.exists(path): 
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

class FixturesSource:
    """
    Manuální/CSV export fixtrů (z Flashscore apod.) => čas, liga, týmy.
    Soubor: fixtures_today.json
    [
      {"league":"LaLiga","home":"Sevilla","away":"Getafe","ts_utc":1730186400},
      ...
    ]
    """
    name = "FIXTURES"
    def fetch_today(self) -> List[MatchFacts]:
        raw = _read_json("fixtures_today.json")
        out: List[MatchFacts] = []
        for r in raw:
            out.append(MatchFacts(
                sport="football",
                league=r["league"], home=r["home"], away=r["away"],
                ts_utc=int(r["ts_utc"]),
                # zbytek doplníme z dalších souborů; zatím None
                home_form10=None, away_form10=None,
                xg_per90_sum=None, pace_hint=None,
                cards_avg=None, corners_avg=None,
                injuries_abs=None, notes=""
            ))
        return out

class UnderstatSource:
    """
    Understat/obdoba – poskytne xG a formu.
    Soubor: understat_today.json
    [
      {"home":"Sevilla","away":"Getafe","xg_sum":2.25,"home_form10":6.5,"away_form10":4.0}
    ]
    """
    name = "UNDERSTAT"
    def fetch_today(self) -> List[MatchFacts]:
        raw = _read_json("understat_today.json")
        now = int(time.time())
        out: List[MatchFacts] = []
        for r in raw:
            out.append(MatchFacts(
                sport="football",
                league=r.get("league",""),
                home=r["home"], away=r["away"],
                ts_utc=r.get("ts_utc", now),  # když chybí, necháme „teď“
                home_form10=r.get("home_form10"),
                away_form10=r.get("away_form10"),
                xg_per90_sum=r.get("xg_sum"),
                pace_hint=None,
                cards_avg=None, corners_avg=None,
                injuries_abs=None, notes="understat"
            ))
        return out

class SofaScoreSource:
    """
    SofaScore/WhoScored – karty/rohy/tempo.
    Soubor: sofascore_today.json
    [
      {"home":"Sevilla","away":"Getafe","league":"LaLiga",
       "corners_avg":9.6,"cards_avg":5.1,"pace_hint":1.08}
    ]
    """
    name = "SOFASCORE"
    def fetch_today(self) -> List[MatchFacts]:
        raw = _read_json("sofascore_today.json")
        now = int(time.time())
        out: List[MatchFacts] = []
        for r in raw:
            out.append(MatchFacts(
                sport="football",
                league=r.get("league",""),
                home=r["home"], away=r["away"],
                ts_utc=r.get("ts_utc", now),
                home_form10=None, away_form10=None,
                xg_per90_sum=None,
                pace_hint=r.get("pace_hint"),
                cards_avg=r.get("cards_avg"),
                corners_avg=r.get("corners_avg"),
                injuries_abs=r.get("injuries_abs"),
                notes="sofascore"
            ))
        return out
