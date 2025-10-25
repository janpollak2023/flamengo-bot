# sources_base.py — agregace a slučování víc zdrojů
from typing import Iterable, Dict, Tuple
from flamengo_strategy import MatchFacts
import unicodedata, re

TIME_TOL_MIN = 120  # větší rozptyl = 2 hodiny

def _slug(x: str) -> str:
    x = unicodedata.normalize("NFKD", x).encode("ascii","ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "", x).lower()

def _fuzzy_key(m: MatchFacts) -> Tuple[str,str,str]:
    # klíč bez času – pro seskupení „Sevilla–Getafe“ napříč zdroji
    return (m.sport, _slug(m.home), _slug(m.away))

def _merge(a: MatchFacts, b: MatchFacts) -> MatchFacts:
    # sloučí informace; čas vezmeme blíže reálnému (ponecháme a.ts pokud už je z Tipsportu)
    ts = a.ts_utc if a.notes.find("tipsport")>=0 else (b.ts_utc or a.ts_utc)
    return MatchFacts(
        sport=a.sport or b.sport,
        league=a.league or b.league,
        home=a.home or b.home,
        away=a.away or b.away,
        ts_utc=ts,
        home_form10=a.home_form10 if a.home_form10 is not None else b.home_form10,
        away_form10=a.away_form10 if a.away_form10 is not None else b.away_form10,
        xg_per90_sum=a.xg_per90_sum if a.xg_per90_sum is not None else b.xg_per90_sum,
        pace_hint=a.pace_hint if a.pace_hint is not None else b.pace_hint,
        cards_avg=a.cards_avg if a.cards_avg is not None else b.cards_avg,
        corners_avg=a.corners_avg if a.corners_avg is not None else b.corners_avg,
        injuries_abs=a.injuries_abs if a.injuries_abs is not None else b.injuries_abs,
        notes=";".join(filter(None,[a.notes,b.notes]))
    )

def _time_close(ts1: int, ts2: int) -> bool:
    return abs(int(ts1)-int(ts2)) <= TIME_TOL_MIN*60

def gather_from_sources(sources: Iterable) -> list[MatchFacts]:
    # 1) nahrát vše
    buckets: Dict[tuple, list[MatchFacts]] = {}
    for s in sources:
        try:
            for m in s.fetch_today():
                buckets.setdefault(_fuzzy_key(m), []).append(m)
        except Exception as e:
            print(f"[WARN] Source {getattr(s,'name',s)} failed: {e}")

    # 2) v každém bucketu vybereme „hlavní čas“ (preferuj Tipsport)
    out: list[MatchFacts] = []
    for _, arr in buckets.items():
        # preferuj záznamy s „tipsport“ v notes
        tips = [x for x in arr if "tipsport" in (x.notes or "")]
        base = tips[0] if tips else arr[0]
        # slouč všechny, které jsou časově blízko
        merged = base
        for x in arr:
            if _time_close(base.ts_utc, x.ts_utc):
                merged = _merge(merged, x)
        out.append(merged)
    return out
