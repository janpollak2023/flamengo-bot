# scraper.py
import re, time, random
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; FlamengoBot/1.0)"}

def get_match_list(category_url:str)->list[dict]:
    r = requests.get(category_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    items = []
    for a in soup.select("a[href*='/kurzy/zapas/']"):
        href = a.get("href")
        title = a.get_text(" ", strip=True)
        if not href or not title: continue
        if not href.startswith("http"): href = "https://m.tipsport.cz"+href
        items.append({"title":title, "url":href})
    return items

def tipsport_stats(match_url:str)->dict:
    # přepni na /statistiky
    stats_url = re.sub(r"/zapas/([^/]+)/(\d+).*", r"/zapas/\1/\2/statistiky", match_url)
    r = requests.get(stats_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    s = BeautifulSoup(r.text, "lxml")
    # příklady extrakcí – budeš doladit dle skutečné stránky
    h2h = s.find(string=re.compile("Vzájemné zápasy", re.I))
    # ... parsuj tabulky „formy“, průměry gólů, 1H/2H distribuce atd.
    return {"h2h":None, "first_half_goal_rate":None}

def livesport_enrich(home:str, away:str)->dict:
    # vyhledání na livesportu (jednoduché query – případně doplnit ručně mapy týmů)
    # doporučeno držet cache
    return {}
