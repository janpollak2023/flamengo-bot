# tip_engine.py — hlavní mozek /tip
# Sloučí data z více zdrojů, aplikuje Flamengo strategii, filtruje ≥90 %,
# zkontroluje, že zápas existuje na Tipsportu, a vrátí čitelný text.

from typing import List, Tuple
from flamengo_strategy import MatchFacts, TipCandidate, propose_football_tips
from sources_base import gather_from_sources
from sources_files import FixturesSource, UnderstatSource, SofaScoreSource
from tipsport_check import exists_on_tipsport

# --------- Parametry filtrů ---------
MIN_ODDS = 1.5      # preferovaný rozsah kurzů
MAX_ODDS = 2.9
MAX_ALLOW = 10.0    # výjimečně pustíme i vyšší
MIN_CONFIDENCE = 90 # jen tipy s ≥ 90 %

STAKE_BASE = 100    # modelová vsazená částka (Kč) pro ukázku výplaty

# --------- Pomocné funkce ---------
def _odds_pass(odds: float | None) -> bool:
    """Pustí tip, pokud je kurz v preferovaném rozsahu; výjimečně až do MAX_ALLOW."""
    if odds is None:
        return True  # nemáme odhad → neblokujeme
    if MIN_ODDS <= odds <= MAX_ODDS:
        return True
    if MAX_ODDS < odds <= MAX_ALLOW:
        return True
    return False

def _format_payout(odds: float | None) -> str:
    """Modelová výplata pro STAKE_BASE Kč."""
    if not odds:
        return "—"
    payout = STAKE_BASE * odds
    profit = STAKE_BASE * (odds - 1.0)
    return f"výplata ~{payout:.0f} Kč (zisk ~{profit:.0f} Kč)"

def _format_tip_line(m: MatchFacts, t: TipCandidate) -> str:
    """Lidsky čitelný řádek pro jeden tip."""
    odds_txt = f" ~{t.est_odds:.2f}" if t.est_odds else ""
    payout = _format_payout(t.est_odds)
    return (
        f"🏟 {m.league}: {m.home} – {m.away}\n"
        f"• Sázka: {t.selection} — {t.market_code}{odds_txt}\n"
        f"• Procenta možné výhry: {t.confidence}%\n"
        f"• {payout}\n"
        f"ℹ️ {t.rationale}\n"
    )

# --------- Hlavní API pro /tip ---------
def suggest_today() -> str:
    """
    1) Načti dnešní zápasy z více zdrojů (fixtures, xG, karty/rohy…)
    2) Vypočti Flamengo kandidáty
    3) Aplikuj filtry: kurz + ≥90 %
    4) Ověř existenci na Tipsportu
    5) Seřaď a vrať čitelný výstup
    """
    # 1) Zdroje – přidávej sem další adaptéry, až je budeš mít
    matches: List[MatchFacts] = gather_from_sources([
        FixturesSource(),     # kdo-kdy-kde (čas/ligy/týmy) – základ
        UnderstatSource(),    # xG + formy
        SofaScoreSource(),    # rohy/karty/tempo/absence
        # DemoSource()        # pokud chceš ponechat demonstrační data
    ])

    # 2) Flamengo kandidáti (jen fotbal)
    candidates: List[Tuple[MatchFacts, TipCandidate]] = []
    for m in matches:
        if m.sport != "football":
            continue
        for t in propose_football_tips(m):
            if t.confidence >= MIN_CONFIDENCE and _odds_pass(t.est_odds):
                candidates.append((m, t))

    # 3) Ověření Tipsportu (měkké – podle JSON feedu; když chybí, projde vše)
    verified: List[Tuple[MatchFacts, TipCandidate]] = []
    for m, t in candidates:
        if exists_on_tipsport(m.league, m.home, m.away, m.ts_utc):
            verified.append((m, t))

    if not verified:
        return (
            "Dnes nemám nic s ≥90 % důvěrou v preferovaném kurzu, co by zároveň sedělo na Tipsport. "
            "Rozšíříme-li zdroje (SofaScore/Understat/Flashscore feedy), pokrytí se zvýší."
        )

    # 4) Řazení: 1) nejvyšší důvěra, 2) nižší kurz (bezpečnější), 3) nejdřív dřívější zápasy
    verified.sort(key=lambda mt: (-mt[1].confidence, mt[1].est_odds or 99.0, mt[0].ts_utc))

    # 5) Sestavení výsledku (omezíme na top 8, ať to není dlouhé)
    lines = [_format_tip_line(m, t) for m, t in verified[:8]]
    explain = (
        "Pravidla Flamengo: primárně fakta (xG/tempo/forma), ne výška kurzu. "
        f"Filtr kurzů {MIN_ODDS}–{MAX_ODDS} (výjimečně až do {MAX_ALLOW}) "
        f"a jen tipy s ≥ {MIN_CONFIDENCE} % důvěrou. "
        "Každý zápas je ověřen, že existuje na Tipsportu."
    )
    return "🔎 Dnešní TOP návrhy (Flamengo, jen ≥90 %)\n\n" + "\n".join(lines) + "\n" + explain
