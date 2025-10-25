# markets.py — definice trhů a mapování na Tipsport
from dataclasses import dataclass
from typing import Optional

# Jednotné názvy trhů (interně)
# — budeme je mapovat na Tipsport při ověřování
@dataclass
class MarketDef:
    code: str          # interní kód
    tipsport_name: str # jak to typicky uvádí Tipsport (orientačně)

# FOTBAL – nejčastější trhy (Tipsport umí všechny níže)
FOOTBALL_MARKETS: list[MarketDef] = [
    MarketDef("FT_OU_1_5",        "Počet gólů v zápase Over 1.5"),
    MarketDef("FT_OU_2_5",        "Počet gólů v zápase Over 2.5"),
    MarketDef("HT_GOAL_YES",      "Padne gól v 1. poločase – ANO"),
    MarketDef("BTTS_YES",         "Oba týmy dají gól – ANO"),
    MarketDef("HOME_OVER_1_5",    "Týmové góly domácí Over 1.5"),
    MarketDef("AWAY_OVER_1_5",    "Týmové góly hosté Over 1.5"),
    MarketDef("ASIAN_HOME_0",     "Asijský handicap 0 (draw no bet) – domácí"),
    MarketDef("ASIAN_AWAY_0",     "Asijský handicap 0 (draw no bet) – hosté"),
    MarketDef("ASIAN_HOME_+0_25", "Asijský handicap +0.25 – domácí"),
    MarketDef("ASIAN_AWAY_+0_25", "Asijský handicap +0.25 – hosté"),
    MarketDef("CARDS_OVER",       "Karty Over (celkem)"),
    MarketDef("CORNERS_OVER",     "Rohy Over (celkem)"),
    MarketDef("HT_CORNERS_OVER",  "Rohy Over – 1. poločas"),
    MarketDef("HT_CARDS_OVER",    "Karty Over – 1. poločas"),
]
