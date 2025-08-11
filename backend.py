from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import time
import threading

app = FastAPI()

# Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOARD_CACHE = []
LAST_UPDATED = 0
CACHE_INTERVAL = 1800  # 30 minutes

HLTV_API_URL = "https://hltv-api-url-here.com"  # Replace with actual scrape logic or API
PRIZEPICKS_API_URL = "https://prizepicks-api-url-here.com"

def scrape_board():
    """
    Scrape HLTV + PrizePicks board and merge into one dataset.
    Replace with your actual scrape logic.
    """
    # Example mock data
    data = [
        {
            "player": "junior",
            "kills_line": 32.5,
            "hs_line": 12.5,
            "salary": 14,
            "team": "BLU",
            "opponent": "CC",
            "match_time": "Today, 8:30 PM",
            "value_score": 10.2
        },
        {
            "player": "laxiee",
            "kills_line": 31.5,
            "hs_line": 17.5,
            "salary": 13,
            "team": "BLU",
            "opponent": "CC",
            "match_time": "Today, 8:30 PM",
            "value_score": 7.8
        }
    ]
    return data

def refresh_cache():
    global BOARD_CACHE, LAST_UPDATED
    while True:
        try:
            print("Refreshing board cache...")
            BOARD_CACHE = scrape_board()
            LAST_UPDATED = time.time()
            print(f"Board updated: {len(BOARD_CACHE)} props cached.")
        except Exception as e:
            print("Error refreshing board:", e)
        time.sleep(CACHE_INTERVAL)

@app.get("/")
def root():
    """
    Root endpoint to check backend status.
    """
    return {
        "message": "Backend is live",
        "props_cached": len(BOARD_CACHE),
        "last_updated": LAST_UPDATED
    }

@app.get("/board")
def get_board():
    """
    Return the latest cached board sorted by value_score (high to low).
    """
    sorted_board = sorted(BOARD_CACHE, key=lambda x: x["value_score"], reverse=True)
    return {
        "last_updated": LAST_UPDATED,
        "props": sorted_board
    }

# Start cache refresh thread
threading.Thread(target=refresh_cache, daemon=True).start()
