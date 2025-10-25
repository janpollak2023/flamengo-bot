# sources_base.py — rozhraní pro datové zdroje (SofaScore/Flashscore/Understat/…)
from typing import Protocol, Iterable
from flamengo_strategy import MatchFacts

class Source(Protocol):
    name: str
    def fetch_today(self) -> list[MatchFacts]: ...

# DEMO zdroj (aby vše běželo hned)
class DemoSource:
    name = "DEMO"
    def fetch_today(self) -> list[MatchFacts]:
        import time
        now = int(time.time())
        return [
            MatchFacts(
                sport="football", league="LaLiga",
                home="Sevilla", away="Getafe",
                ts_utc=now + 3600,
                home_form10=6.5, away_form10=4.0,
                xg_per90_sum=2.25, pace_hint=1.05,
                cards_avg=5.2, corners_avg=9.4,
                injuries_abs=1, notes="Ofenzivní trend posledních 5 zápasů."
            ),
        ]

def gather_from_sources(sources: Iterable[Source]) -> list[MatchFacts]:
    data: list[MatchFacts] = []
    for s in sources:
        try:
            data.extend(s.fetch_today())
        except Exception as e:
            print(f"[WARN] Source {getattr(s,'name',s)} failed: {e}")
    # unikátní zápasy (podle home-away-time)
    key = lambda m: (m.sport, m.league, m.home, m.away, m.ts_utc)
    uniq = {key(m): m for m in data}
    return list(uniq.values())
