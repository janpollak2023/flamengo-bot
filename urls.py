# urls.py – centrální registr Tipsport kategorií

from typing import Dict

# Kanonické kategorie → URL (Tipsport – mobilní web)
URL_MAP: Dict[str, str] = {
    "fotbal":  "https://m.tipsport.cz/kurzy/fotbal-16",
    "hokej":   "https://m.tipsport.cz/kurzy/ledni-hokej-23",
    "tenis":   "https://m.tipsport.cz/kurzy/tenis-43",
    "basket":  "https://m.tipsport.cz/kurzy/basketbal-7",
    "esport":  "https://m.tipsport.cz/kurzy/esporty-188",
}

# Synonyma / zkratky → kanonický klíč
ALIASES: Dict[str, str] = {
    "soccer": "fotbal",
    "football": "fotbal",
    "nhl": "hokej",
    "ledni-hokej": "hokej",
    "basketbal": "basket",
    "csgo": "esport",
    "esports": "esport",
}

def normalize_cat(cat: str) -> str:
    c = (cat or "").strip().lower()
    return ALIASES.get(c, c)

def get_url(cat: str) -> str:
    """Vrátí URL pro kategorii (podporuje aliasy). Default = fotbal."""
    c = normalize_cat(cat)
    return URL_MAP.get(c, URL_MAP["fotbal"])

def categories() -> Dict[str, str]:
    """Pro výpis/diagnostiku."""
    return dict(URL_MAP)
