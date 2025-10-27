from dataclasses import dataclass
from typing import Optional

@dataclass
class TeamStats:
    form5_pts: float          # body z posledních 5 (3-1-0 → 3, 1, 0)
    gf_pg: float              # góly za zápas
    ga_pg: float              # góly proti
    first_half_goal_rate: float  # % zápasů s gólem v 1H
    btts_rate: float
    injuries_key: int         # počet klíčových absencí
    home_adv: bool

def clamp(x, a=0, b=100): return max(a, min(b, x))

def conf_over05_1H(home: TeamStats, away: TeamStats, h2h_1h_rate: float) -> int:
    base = 50
    base += (home.first_half_goal_rate + away.first_half_goal_rate - 100) * 0.25
    base += (home.gf_pg + away.gf_pg - 2.4) * 6
    base += (away.ga_pg + home.ga_pg - 2.2) * 4
    base += (h2h_1h_rate - 50) * 0.2
    base += 4 if home.home_adv else 0
    base -= (home.injuries_key + away.injuries_key) * 1.5
    return int(clamp(round(base)))

def conf_btts(home: TeamStats, away: TeamStats, h2h_btts_rate: float) -> int:
    base = 45
    base += (home.gf_pg + away.gf_pg - 2.6) * 7
    base -= abs(home.form5_pts - away.form5_pts) * 1.2
    base += (home.btts_rate + away.btts_rate - 100) * 0.35
    base += (h2h_btts_rate - 50) * 0.25
    return int(clamp(round(base)))
