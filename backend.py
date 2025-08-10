@app.get("/props")
def get_props():
    props = scrape_prizepicks_board()  # your scraper function
    evaluated_props = []

    for prop in props:
        value_score = calculate_value_score(prop)  # your existing formula
        verdict = "Good Value" if value_score >= 8 else "Low Value"
        
        evaluated_props.append({
            "player": prop["player"],
            "line": prop["line"],
            "type": prop["type"],
            "value_score": round(value_score, 2),
            "verdict": verdict
        })

    # Filter good value props
    good_value_props = [p for p in evaluated_props if p["value_score"] >= 8]

    # If none meet threshold, show top 10 by score
    if not good_value_props:
        good_value_props = sorted(evaluated_props, key=lambda x: x["value_score"], reverse=True)[:10]

    return {"props": good_value_props}
