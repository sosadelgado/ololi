# backend.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
import time

app = FastAPI(title="Bolt Backend - Ranker")

# CORS - open for now (you can lock to your Vercel domain later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory cache for HLTV player stats: {player_lower: (timestamp, data)}
HLTV_CACHE: Dict[str, Any] = {}
HLTV_CACHE_TTL = 30 * 60  # 30 minutes

ROUNDS_PER_MAP = 26  # baseline used for estimates (2-map average)

# Value thresholds
GOOD_THRESHOLD = 12.5
MIN_SHOW_THRESHOLD = 8.0  # lowered threshold so we always show something

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class PropIn(BaseModel):
    player: str
    kills: Optional[float] = None       # PrizePicks kills line (e.g. 32.5)
    hs: Optional[float] = None          # Headshot line (e.g. 12.5)
    salary: Optional[float] = None      # prizepick salary estimate (e.g. 15)
    map_count: Optional[int] = 2        # default to maps 1-2


class RankedProp(BaseModel):
    player: str
    kills: Optional[float]
    hs: Optional[float]
    salary: Optional[float]
    map_count: int
    used_kpr: Optional[float]
    used_hs_pct: Optional[float]
    expected_kills: Optional[float]
    value_score: float
    good: bool
    tier: str
    notes: Optional[str] = None


def fetch_hltv_stats(player_name: str) -> Optional[Dict[str, float]]:
    """
    Try to fetch kpr and hs% from HLTV search -> player page.
    Returns {"kpr": float, "hs_pct": float} or None on failure.
    Caching used to avoid hammering HLTV.
    """
    key = player_name.strip().lower()
    now = time.time()
    cached = HLTV_CACHE.get(key)
    if cached and now - cached["ts"] < HLTV_CACHE_TTL:
        return cached["data"]

    try:
        # HLTV quick search page
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        search_url = f"https://www.hltv.org/search?query={requests.utils.quote(player_name)}"
        r = s.get(search_url, timeout=10)
        if r.status_code != 200:
            HLTV_CACHE[key] = {"ts": now, "data": None}
            return None

        soup = BeautifulSoup(r.text, "lxml")
        # Find first player link (best-effort)
        link = soup.select_one("a[href^='/player/']")
        if not link:
            HLTV_CACHE[key] = {"ts": now, "data": None}
            return None

        player_href = link.get("href")
        player_url = "https://www.hltv.org" + player_href
        r2 = s.get(player_url, timeout=10)
        if r2.status_code != 200:
            HLTV_CACHE[key] = {"ts": now, "data": None}
            return None

        soup2 = BeautifulSoup(r2.text, "lxml")

        # Best-effort scraping: HLTV layout changes sometimes — handle gracefully
        # We'll search for "KPR" and "HS%" occurrences in the raw text as fallback
        page_text = soup2.get_text(" ", strip=True)

        # Try structured selectors first (if present)
        kpr = None
        hs_pct = None

        # find lines like "KPR 0.86" or "HS 43%"
        import re
        kpr_m = re.search(r"KPR\s*([\d.]+)", page_text)
        hs_m = re.search(r"HS\s*([\d.]+)%", page_text)

        if kpr_m:
            kpr = float(kpr_m.group(1))
        if hs_m:
            hs_pct = float(hs_m.group(1)) / 100.0

        # store result (even if None) to avoid rapid repeat scraping
        data = None
        if kpr is not None or hs_pct is not None:
            data = {"kpr": kpr or None, "hs_pct": hs_pct or None}
        HLTV_CACHE[key] = {"ts": now, "data": data}
        return data
    except Exception:
        HLTV_CACHE[key] = {"ts": now, "data": None}
        return None


def calculate_value_and_meta(prop: PropIn) -> RankedProp:
    """
    Compute value score using:
      value_score = (hs_pct * 0.65 + kpr * 0.35) * 100 - salary
    Where:
      - kpr is either HLTV KPR or estimated from kills/rounds
      - hs_pct is HLTV HS% or estimated as hs/kills
      - expected_kills = kpr * map_count * ROUNDS_PER_MAP
    Returns RankedProp
    """
    # defaults
    salary = float(prop.salary) if prop.salary is not None else 15.0
    map_count = int(prop.map_count or 2)
    kills_line = float(prop.kills) if prop.kills is not None else None
    hs_line = float(prop.hs) if prop.hs is not None else None

    notes = []
    used_kpr = None
    used_hs_pct = None

    # Try HLTV
    hltv = fetch_hltv_stats(prop.player)
    if hltv:
        used_kpr = hltv.get("kpr")
        used_hs_pct = hltv.get("hs_pct")
        notes.append("HLTV stats used")
    # Fallbacks
    if used_kpr is None:
        if kills_line is not None:
            # estimate KPR from PrizePicks kill line assuming baseline rounds per map
            estimated_kpr = kills_line / (map_count * ROUNDS_PER_MAP)
            used_kpr = round(estimated_kpr, 4)
            notes.append("KPR estimated from kills line")
        else:
            used_kpr = 0.0
            notes.append("KPR defaulted to 0")

    if used_hs_pct is None:
        if hs_line is not None and kills_line:
            est_hs_pct = hs_line / kills_line if kills_line > 0 else 0.0
            used_hs_pct = round(est_hs_pct, 4)
            notes.append("HS% estimated from hs & kills lines")
        else:
            used_hs_pct = 0.0
            notes.append("HS% defaulted to 0")

    expected_kills = used_kpr * map_count * ROUNDS_PER_MAP

    # value_score formula (matching manual calcs)
    value_score = (used_hs_pct * 0.65 + used_kpr * 0.35) * 100.0 - salary
    value_score = round(value_score, 2)

    # good flag & tier
    good = value_score >= GOOD_THRESHOLD
    if value_score >= GOOD_THRESHOLD:
        tier = "lock"
    elif value_score >= MIN_SHOW_THRESHOLD:
        tier = "solid"
    else:
        tier = "avoid"

    rp = RankedProp(
        player=prop.player,
        kills=prop.kills,
        hs=prop.hs,
        salary=salary,
        map_count=map_count,
        used_kpr=used_kpr,
        used_hs_pct=used_hs_pct,
        expected_kills=round(expected_kills, 2),
        value_score=value_score,
        good=good,
        tier=tier,
        notes="; ".join(notes)
    )
    return rp


@app.get("/health")
def health():
    return {"status": "bolt-backend live"}


@app.post("/rank", response_model=Dict[str, Any])
def rank_board(props: List[PropIn]):
    """
    Accepts a JSON array of props (player, kills, hs, salary, map_count) and returns:
      { "status": "ok", "props": [ RankedProp... ] }
    """
    if not isinstance(props, list) or len(props) == 0:
        raise HTTPException(status_code=400, detail="Send a non-empty array of props")

    ranked = [calculate_value_and_meta(PropIn(**p.dict())) if isinstance(p, PropIn) else calculate_value_and_meta(PropIn(**p)) for p in props]
    # sort best -> worst
    ranked_sorted = sorted(ranked, key=lambda x: x.value_score, reverse=True)

    # return serializable data
    return {"status": "ok", "props": [r.dict() for r in ranked_sorted]}

