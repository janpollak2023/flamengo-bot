# sources_base.py — agregace z více zdrojů + chytré slučování
from typing import Iterable, Dict, Tuple
from flamengo_strategy import MatchFacts

class Source:
    name: str
    def fetch_today(self) -> list[MatchFacts]: ...

def _key(m: MatchFacts) -> Tuple[str,str,str,str,int]:
    return (m.sport, m.league, m.home, m.away, int(m.ts_utc))

def _merge(a: MatchFacts, b: MatchFacts) -> MatchFacts:
    # doplníme None hodnoty z druhého zdroje
    return MatchFacts(
        sport=a.sport or b.sport,
        league=a.league or b.league,
        home=a.home or b.home,
        away=a.away or b.away,
        ts_utc=a.ts_utc or b.ts_utc,
        home_form10=a.home_form10 if a.home_form10 is not None else b.home_form10,
        away_form10=a.away_form10 if a.away_form10 is not None else b.away_form10,
        xg_per90_sum=a.xg_per90_sum if a.xg_per90_sum is not None else b.xg_per90_sum,
        pace_hint=a.pace_hint if a.pace_hint is not None else b.pace_hint,
        cards_avg=a.cards_avg if a.cards_avg is not None else b.cards_avg,
        corners_avg=a.corners_avg if a.corners_avg is not None else b.corners_avg,
        injuries_abs=a.injuries_abs if a.injuries_abs is not None else b.injuries_abs,
        notes=";".join(filter(None, [a.notes, b.notes]))
    )

def gather_from_sources(sources: Iterable[Source]) -> list[MatchFacts]:
    bykey: Dict[tuple, MatchFacts] = {}
    for s in sources:
        try:
            for m in s.fetch_today():
                k = _key(m)
                if k in bykey:
                    bykey[k] = _merge(bykey[k], m)
                else:
                    bykey[k] = m
        except Exception as e:
            print(f"[WARN] Source {getattr(s,'name',s)} failed: {e}")
    return list(bykey.values())
