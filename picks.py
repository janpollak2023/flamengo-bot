# picks.py
from analyzer import TeamStats, conf_over05_1H, conf_btts

def make_picks(stats_home, stats_away, h2h):
    picks = []

    c1 = conf_over05_1H(stats_home, stats_away, h2h.get("1H_rate", 50))
    if c1 >= 80:
        picks.append({
            "market_key":"goly_prvni_polo_over05",
            "market_label":"Over 0.5 gól v 1. poločase",
            "confidence_pct":c1,
            "bucket":"BEZPEČNÉ",
            "reason":"Vysoké 1H rate obou týmů + slušná ofenziva, H2H potvrzuje."
        })

    c2 = conf_btts(stats_home, stats_away, h2h.get("btts_rate", 50))
    bucket = "BEZPEČNÉ" if c2>=80 else ("RISK" if c2>=70 else "SKIP")
    if c2>=70:
        picks.append({
            "market_key":"oba_tymy_gol",
            "market_label":"Oba týmy dají gól",
            "confidence_pct":c2,
            "bucket":bucket,
            "reason":"Oba týmy pravidelně skórují; obrany propouští."
        })
    return picks
