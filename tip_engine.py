# tip_engine.py — Flamengo výběr nad Tipsport-first pipeline
from typing import List, Tuple
from flamengo_strategy import MatchFacts, TipCandidate, propose_football_tips
from sources_base import gather_from_sources
from sources_files import TipsportFixturesSource, FixturesSource, UnderstatSource, SofaScoreSource
from tipsport_check import exists_on_tipsport

MIN_ODDS = 1.5
MAX_ODDS = 2.9
MAX_ALLOW = 10.0
MIN_CONFIDENCE = 90
STAKE_BASE = 100

def _odds_pass(odds: float | None) -> bool:
    if odds is None: return True
    if MIN_ODDS <= odds <= MAX_ODDS: return True
    if MAX_ODDS < odds <= MAX_ALLOW: return True
    return False

def _payout(odds: float | None) -> str:
    if not odds: return "—"
    gross = STAKE_BASE * odds
    net = STAKE_BASE * (odds - 1.0)
    return f"výplata ~{gross:.0f} Kč (zisk ~{net:.0f} Kč)"

def _format_line(m: MatchFacts, t: TipCandidate) -> str:
    odds_txt = f" ~{t.est_odds:.2f}" if t.est_odds else ""
    return (
        f"🏟 {m.league}: {m.home} – {m.away}\n"
        f"• Sázka: {t.selection} — {t.market_code}{odds_txt}\n"
        f"• Procenta možné výhry: {t.confidence}%\n"
        f"• {_payout(t.est_odds)}\n"
        f"ℹ️ {t.rationale}\n"
    )

def suggest_today() -> str:
    # 1) ZAČNI TIPSPORTEM → jen zápasy, které Tipsport nabízí
    matches: List[MatchFacts] = gather_from_sources([
        TipsportFixturesSource(),  # primární (šířka vyhledávání určuje tento soubor)
        FixturesSource(),          # případné doplňující fixtry (větší rozptyl času/lig)
        UnderstatSource(),         # xG + formy
        SofaScoreSource(),         # karty/rohy/tempo/absence
    ])

    # 2) Flamengo kandidáti (jen fotbal), ≥90 % a kurzový filtr
    cands: List[Tuple[MatchFacts, TipCandidate]] = []
    for m in matches:
        if m.sport != "football": 
            continue
        for t in propose_football_tips(m):
            if t.confidence >= MIN_CONFIDENCE and _odds_pass(t.est_odds):
                cands.append((m, t))

    if not cands:
        return "Z Tipsport nabídky dnes nic nesplnilo ≥90 % důvěru v požadovaných kurzech."

    # 3) Druhé ověření Tipsportu (když je feed chudý – ponecháme, jinak znovu check)
    verified: List[Tuple[MatchFacts, TipCandidate]] = []
    for m, t in cands:
        if exists_on_tipsport(m.league, m.home, m.away, m.ts_utc):
            verified.append((m, t))

    if not verified:
        return "Zápasy z analýzy nejsou (po ověření) v Tipsportu — doplň feed tipsport_today.json."

    # 4) Seřaď: vyšší důvěra → nižší kurz → dřívější zápas
    verified.sort(key=lambda mt: (-mt[1].confidence, mt[1].est_odds or 99.0, mt[0].ts_utc))

    # 5) Výstup
    lines = [_format_line(m, t) for m, t in verified[:12]]  # větší rozptyl → klidně 12 tipů
    tail = (
        f"Pravidla Flamengo: fakta (xG/forma/tempo), filtr kurzů {MIN_ODDS}–{MAX_ODDS} "
        f"(výjimečně až do {MAX_ALLOW}), pouze tipy s ≥{MIN_CONFIDENCE} % důvěrou. "
        "Vstupní množina = zápasy dostupné na Tipsportu (tipsport_today.json)."
    )
    return "🔎 Dnešní TOP návrhy (Tipsport → Flamengo)\n\n" + "\n".join(lines) + "\n" + tail
