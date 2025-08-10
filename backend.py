from fastapi import FastAPI
import requests

app = FastAPI()

# === CONFIG ===
VALUE_THRESHOLD = 8.0

# Example HS/Kill Combo formula
def calculate_value_score(kill_line: float, hs_line: float, salary: float):
    try:
        return (hs_line * 0.65 + kill_line * 0.35) - salary
    except Exception:
        return 0.0

# Example scraping function (replace with your real logic)
def scrape_prizepicks_board():
    # Here’s a dummy board for testing — replace with real scraping call
    return [
        {"player": "junior", "kill_line": 32.5, "hs_line": 12.5, "salary": 15, "type": "kills"},
        {"player": "laxiee", "kill_line": 31.5, "hs_line": 17.5, "salary": 14, "type": "kills"},
        {"player": "Walco", "kill_line": 29.5, "hs_line": 14.5, "salary": 14, "type": "kills"},
        {"player": "REKMEISTER", "kill_line": 28.5, "hs_line": 13.5, "salary": 14, "type": "kills"},
    ]

@app.get("/props")
def get_props():
    raw_props = scrape_prizepicks_board()
    evaluated_props = []

    for prop in raw_props:
        value_score = calculate_value_score(
            prop["kill_line"],
            prop["hs_line"],
            prop["salary"]
        )
        verdict = "Good Value" if value_score >= VALUE_THRESHOLD else "Low Value"

        evaluated_props.append({
            "player": prop["player"],
            "kill_line": prop["kill_line"],
            "hs_line": prop["hs_line"],
            "salary": prop["salary"],
            "type": prop["type"],
            "value_score": round(value_score, 2),
            "verdict": verdict
        })

    # Filter for good value props
    good_value_props = [p for p in evaluated_props if p["value_score"] >= VALUE_THRESHOLD]

    # If none meet threshold, return top 10 by score
    if not good_value_props:
        good_value_props = sorted(evaluated_props, key=lambda x: x["value_score"], reverse=True)[:10]

    return {"props": good_value_props}
