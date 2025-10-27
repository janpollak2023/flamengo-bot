# schema.py
ANALYSIS_SCHEMA_EXAMPLE = {
    "match_id": "napoli-frankfurt-7374869",
    "comp": "Liga mistrů",
    "kickoff_cet": "2025-11-04T18:45:00+01:00",
    "sources": {
        "tipsport": "https://m.tipsport.cz/kurzy/zapas/fotbal-napoli-frankfurt/7374869/statistiky",
        "livesport": "https://www.livesport.cz"
    },
    "summary": {
        "home": {"form_last5": [1,1,0,1,1], "avg_gf": 2.0, "avg_ga": 0.8, "home_adv": True},
        "away": {"form_last5": [0,1,0,0,1], "avg_gf": 1.1, "avg_ga": 1.7},
        "injuries_key": 1,
        "h2h_last5_home_scored": 4,
        "first_goal_window": "12'–28'"
    },
    "picks": [
        {
            "market_key": "goly_prvni_polo_over05",
            "market_label": "Over 0.5 gól v 1. poločase",
            "confidence_pct": 88,
            "reason": "Oba týmy >1.2 xGF/1H, 4/5 posledních H2H gól do 30'.",
            "odds": None,  # doplní se, když je dostupné
            "bucket": "BEZPEČNÉ"
        },
        {
            "market_key": "oba_tymy_gol",
            "market_label": "Oba týmy dají gól (BTTS)",
            "confidence_pct": 76,
            "reason": "Hosté inkasují, ale skórují venku 7/10.",
            "odds": None,
            "bucket": "RISK"
        }
    ],
    "decision": "SÁZET pouze BEZPEČNÝ pick (≥80 %)."
}
