# tip_engine.py — hlavní mozek /tip (Flamengo + filtry + Tipsport check)
from typing import Iterable
from flamengo_strategy import MatchFacts, TipCandidate, propose_football_tips
from sources_base import gather_from_sources, DemoSource
from tipsport_check import exists_on_tipsport

# Filtry
MIN_ODDS = 1.5
MAX_ODDS = 2.9     # preferujeme spodní hranici
MAX_ALLOW = 10.0   # povolíme i vyšší „bomba“ tip
MIN_CONFIDENCE = 90  # 💥 jen 90 % a víc

STAKE_BASE = 100  # modelová vsazená částka pro výpočet výplaty (Kč)

def _odds_pass(odds: float | None) -> bool:
    if odds is None:
        return True
    if MIN_ODDS <= odds <= MAX_ODDS:
        return True
    if MAX_ODDS < odds <= MAX_ALLOW:
        return True
    return False

def _format_payout(odds: float | None) -> str:
    if not odds:
        return "—"
    payout = STAKE_BASE * odds           # celková výplata
    profit = STAKE_BASE * (odds - 1.0)   # čistý zisk
    return f"výplata ~{payout:.0f} Kč (zisk ~{profit:.0f} Kč)"

def _format_tip_line(m: MatchFacts, t: TipCandidate) -> str:
    payout = _format_payout(t.est_odds)
    odds_txt = f" ~{t.est_odds:.2f}" if t.est_odds else ""
    return (
        f"🏟 {m.league}: {m.home} – {m.away}\n"
        f"• Sázka: {t.selection} — {t.market_code}{odds_txt}\n"
        f"• Procenta možné výhry: {t.confidence}%\n"
        f"• {payout}\n"
        f"ℹ️ {t.rationale}\n"
    )

def suggest_today() -> str:
    # 1) stáhnout dnešní zápasy (zatím DEMO, pak přidáme další adaptéry)
    matches = gather_from_sources([DemoSource()])

    # 2) vygenerovat kandidáty (Flamengo) a aplikovat filtry kurz + min. 90 %
    all_tips: list[tuple[MatchFacts, TipCandidate]] = []
    for m in matches:
        if m.sport != "football":
            continue
        for t in propose_football_tips(m):
            if t.confidence >= MIN_CONFIDENCE and _odds_pass(t.est_odds):
                all_tips.append((m, t))

    # 3) ověřit, že zápas existuje na Tipsportu
    verified: list[tuple[MatchFacts, TipCandidate]] = []
    for m, t in all_tips:
        if exists_on_tipsport(m.league, m.home, m.away, m.ts_utc):
            verified.append((m, t))

    if not verified:
        return (
            "Dnes nemám nic s ≥90 % důvěrou, co by zároveň sedělo na Tipsport. "
            "Jakmile přidáme další zdroje (SofaScore/Understat/Flashscore), pokrytí se rozšíří."
        )

    # 4) seřadit: nejdřív nejvyšší důvěra, pak nižší kurz (preferujeme bezpečí)
    verified.sort(key=lambda mt: (-mt[1].confidence, mt[1].est_odds or 99.0))

    # 5) sestavit výstup
    lines = [_format_tip_line(m, t) for m, t in verified[:8]]  # pošleme top 8
    explain = (
        "Pravidla Flamengo: primárně fakta (xG/tempo/forma), ne kurz. "
        "Filtrujeme kurzy 1.5–2.9 (povolíme až do 10 u silných signálů) "
        "a posíláme jen tipy s ≥90 % důvěrou. Každý zápas ověřujeme, že je na Tipsportu."
    )
    return "🔎 Dnešní TOP návrhy (Flamengo, jen ≥90 %)\n\n" + "\n".join(lines) + "\n" + explain
