# tip_engine.py — Flamengo výběr nad Tipsport-first pipeline
# Filtry: jen zápasy z Tipsportu, start do 3 hodin, 1–10 tipů
from typing import List, Tuple
import time
from flamengo_strategy import MatchFacts, TipCandidate, propose_football_tips
from sources_base import gather_from_sources
from sources_files import TipsportFixturesSource, FixturesSource, UnderstatSource, SofaScoreSource
from tipsport_check import exists_on_tipsport

# ------- Parametry -------
MIN_ODDS = 1.3
MAX_ODDS = 2.9
MAX_ALLOW = 10.0
MIN_CONF_PRIMARY = 85       # hlavní práh
MIN_CONF_FALLBACK = 75      # nouzový práh, když nic nesplní 90
KICKOFF_WINDOW_H = 8        # jen zápasy, které začnou do 3 hodin
MAX_COUNT = 10              # vezmeme max. 10 tipů
STAKE_BASE = 100            # modelová vsazená částka (Kč)

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
    when = time.strftime("%H:%M", time.gmtime(m.ts_utc)) + " UTC"
    return (
        f"🏟 {m.league}: {m.home} – {m.away} • výkop {when}\n"
        f"• Sázka: {t.selection} — {t.market_code}{odds_txt}\n"
        f"• Procenta možné výhry: {t.confidence}%\n"
        f"• {_payout(t.est_odds)}\n"
        f"ℹ️ {t.rationale}\n"
    )

def _within_window(ts_utc: int, now: float) -> bool:
    return ts_utc >= now and ts_utc <= now + KICKOFF_WINDOW_H * 3600

def _pick_candidates(matches: List[MatchFacts], min_conf: int) -> List[Tuple[MatchFacts, TipCandidate]]:
    cands: List[Tuple[MatchFacts, TipCandidate]] = []
    for m in matches:
        if m.sport != "football":
            continue
        for t in propose_football_tips(m):
            if t.confidence >= min_conf and _odds_pass(t.est_odds):
                cands.append((m, t))
    return cands

def suggest_today() -> str:
    # 1) Primárně Tipsport → aby šly vsadit
    matches: List[MatchFacts] = gather_from_sources([
        TipsportFixturesSource(),  # určující množina
        FixturesSource(),          # doplněk
        UnderstatSource(),         # xG + formy
        SofaScoreSource(),         # karty/rohy/tempo/absence
    ])

    # 2) Jen zápasy, které začínají do 3 hodin
    now = time.time()
    matches = [m for m in matches if _within_window(m.ts_utc, now)]

    if not matches:
        return f"Do {KICKOFF_WINDOW_H} hodin nemám žádné zápasy v Tipsport nabídce."

    # 3) Flamengo kandidáti s hlavním prahem
    cands = _pick_candidates(matches, MIN_CONF_PRIMARY)

    # 4) Druhé ověření Tipsportu (pro jistotu)
    verified: List[Tuple[MatchFacts, TipCandidate]] = []
    for m, t in cands:
        if exists_on_tipsport(m.league, m.home, m.away, m.ts_utc):
            verified.append((m, t))

    # 5) Pokud nic, zkus fallback ≥85 % (pořád jen do 3 hodin)
    used_fallback = False
    if not verified:
        cands_fb = _pick_candidates(matches, MIN_CONF_FALLBACK)
        for m, t in cands_fb:
            if exists_on_tipsport(m.league, m.home, m.away, m.ts_utc):
                verified.append((m, t))
        used_fallback = bool(verified)

    if not verified:
        return (
            f"V Tipsport nabídce do {KICKOFF_WINDOW_H} h teď nic nesplnilo ani {MIN_CONF_FALLBACK}% "
            f"v kurzech {MIN_ODDS}–{MAX_ODDS} (výjimečně ≤ {MAX_ALLOW})."
        )

    # 6) Seřadit: důvěra ↓, kurz ↑ (preferuj nižší), výkop ↑
    verified.sort(key=lambda mt: (-mt[1].confidence, mt[1].est_odds or 99.0, mt[0].ts_utc))

    # 7) Omezit na 1–10 tipů
    shown = verified[:MAX_COUNT]

    # 8) Výstup
    header = "🔎 Dnešní TOP návrhy (Tipsport → Flamengo, výkop ≤ 3 h)\n"
    if used_fallback:
        header += f"⚠️ Použit fallback ≥{MIN_CONF_FALLBACK} % (žádný tip nesplnil {MIN_CONF_PRIMARY} %).\n\n"
    else:
        header += f"✅ Vše s ≥{MIN_CONF_PRIMARY} % důvěrou.\n\n"

    lines = [_format_line(m, t) for m, t in shown]
    tail = (
        f"Pravidla Flamengo: fakta (xG/forma/tempo), filtr kurzů {MIN_ODDS}–{MAX_ODDS} "
        f"(výjimečně až do {MAX_ALLOW}). Vstup = zápasy dostupné na Tipsportu."
    )
    return header + "\n".join(lines) + "\n" + tail
