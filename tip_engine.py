# tip_engine.py — hlavní mozek /tip
from typing import Iterable
from flamengo_strategy import MatchFacts, TipCandidate, propose_football_tips
from sources_base import gather_from_sources, DemoSource
from tipsport_check import exists_on_tipsport

MIN_ODDS = 1.5
MAX_ODDS = 2.9     # preferujeme spodní hranici
MAX_ALLOW = 10.0   # pustíme i vyšší (když je to bomba), ale nepreferujeme

def _odds_pass(odds: float | None) -> bool:
    if odds is None:
        return True
    if odds >= MIN_ODDS and odds <= MAX_ODDS:
        return True
    if odds > MAX_ODDS and odds <= MAX_ALLOW:
        return True
    return False

def _format_tip_line(t: TipCandidate) -> str:
    est = f" (odhad kurzu ~{t.est_odds:.2f})" if t.est_odds else ""
    return f"• {t.selection} — {t.market_code}  — {t.confidence}%{est}\n  ℹ️ {t.rationale}"

def suggest_today() -> str:
    # 1) stáhnout dnešní zápasy ze všech zdrojů
    matches = gather_from_sources([DemoSource()])  # ← přidej další adaptéry

    # 2) vygenerovat kandidáty podle Flamengo
    all_tips: list[tuple[MatchFacts, TipCandidate]] = []
    for m in matches:
        if m.sport != "football":
            continue
        tips = propose_football_tips(m)
        for t in tips:
            if _odds_pass(t.est_odds):
                all_tips.append((m, t))

    # 3) ověřit existenci na Tipsportu
    verified: list[tuple[MatchFacts, TipCandidate]] = []
    for m, t in all_tips:
        if exists_on_tipsport(m.league, m.home, m.away, m.ts_utc):
            verified.append((m, t))

    if not verified:
        return "Dnes nic vhodného nebo Tipsport nenabízí odpovídající zápas."

    # 4) seřadit podle důvěry (preferujeme nižší kurzy – ty mají vyšší conf v návrhu)
    verified.sort(key=lambda mt: (-mt[1].confidence, mt[1].est_odds or 99))

    # 5) sestavit výstup (fotbal rozděleně a srozumitelně)
    lines = []
    for m, t in verified[:8]:  # pošleme top 8
        header = f"🏟 {m.league}: {m.home} – {m.away}"
        tipline = _format_tip_line(t)
        lines.append(f"{header}\n{tipline}\n")

    explain = (
        "Pravidla Flamengo: primárně fakta (xG/tempo/forma), ne kurz. "
        "Filtr kurzů 1.5–2.9 (preferujeme nižší), pustíme až do 10. "
        "Každý návrh je ověřen, že zápas existuje na Tipsportu."
    )
    return "🔎 Dnešní návrhy (Flamengo)\n\n" + "\n".join(lines) + "\n" + explain
