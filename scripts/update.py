#!/usr/bin/env python3
"""Update data.json. Thai: automatic via lotto.api.rayriffy.com. Lao/Hanoi: manual.csv (+ optional lao_urls).
Usage: python scripts/update.py [--pages N] [--limit N] [--selftest]"""
import json, re, sys, os, csv, time, urllib.request
from datetime import datetime, timezone
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data.json")
API = "https://lotto.api.rayriffy.com"
LEN = {"thai": 6, "lao": 4, "hanoi": 4}  # stored as STRINGS so leading zeros survive

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lottery-analyzer-personal/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")

def add(db, t, date, variant, number, last2=None, extra=None, src=None):
    number = str(number).strip()
    if t not in LEN or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date): return False
    try: datetime.strptime(date, "%Y-%m-%d")
    except ValueError: return False
    if not (number.isdigit() and len(number) == LEN[t]): return False
    if any(x["type"] == t and x["date"] == date and x.get("variant") == variant for x in db["draws"]): return False
    db["draws"].append({"type": t, "date": date, "variant": variant, "number": number,
                        "last2": last2 or number[-2:], "extra": extra or {}, **({"src": src} if src else {})})
    return True

def thai(db, pages, limit):
    n = 0
    for p in range(1, pages + 1):
        for it in json.loads(get(f"{API}/list/{p}"))["response"]:
            i = it["id"]  # DDMMYYYY (Buddhist year)
            date = f"{int(i[4:]) - 543:04d}-{i[2:4]}-{i[:2]}"
            if any(x["type"] == "thai" and x["date"] == date for x in db["draws"]): continue
            if n >= limit: return n
            r = json.loads(get(f"{API}/lotto/{i}"))["response"]
            first = next(q for q in r["prizes"] if q["id"] == "prizeFirst")["number"][0]
            rn = {q["id"]: q["number"] for q in r["runningNumbers"]}
            ok = add(db, "thai", date, "main", first, rn["runningNumberBackTwo"][0],
                     {"front3": rn["runningNumberFrontThree"], "back3": rn["runningNumberBackThree"]})
            n += ok; time.sleep(0.5)
    return n

def ce(y):
    y = int(y); y += 2500 if y < 100 else 0
    return y - 543 if y > 2400 else y

def lao_from_text(db, text):  # matches rows like "19/10/2026 6331 331 31"
    text = re.sub(r"<[^>]+>", " ", text); n = 0
    for d, m, y, n4 in re.findall(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s+(\d{4})\s+\d{3}\s+\d{1,2}\b", text):
        n += add(db, "lao", f"{ce(y):04d}-{int(m):02d}-{int(d):02d}", "main", n4)
    return n

def gemini_fetch(db):
    """Lao + Hanoi(normal) via Gemini with Google Search. Key comes ONLY from the GEMINI_API_KEY secret.
    Results are LLM-extracted: validated, flagged src=gemini (shown with a warning in the page)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key: print("GEMINI_API_KEY secret not set - skipping Lao/Hanoi auto-update"); return 0
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    today = datetime.now(timezone.utc).date()
    prompt = (f"Today is {today}. Use web search to find ACTUAL published results for the last 10 days of: "
      "(1) Lao lottery 'หวยลาวพัฒนา' (draws Mon-Fri evening): the 6-digit first number; "
      "(2) Hanoi 'หวยฮานอยปกติ' as published by Thai lottery news sites: the 4-digit number and the 2-digit lower number. "
      "Only include draws you found in a source; never guess or invent. Reply with ONLY a JSON array, e.g. "
      '[{"type":"lao","date":"2026-10-19","number":"046331"},{"type":"hanoi","date":"2026-10-19","number":"4736","lower2":"86"}]. '
      "Dates are CE YYYY-MM-DD. Numbers are strings with leading zeros kept.")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]}).encode()
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    j = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    text = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"])
    m = re.search(r"\[.*\]", text, re.S)
    n = 0
    for it in json.loads(m.group(0)) if m else []:
        try:
            t, date, num = it["type"], it["date"], str(it["number"]).strip()
            d = datetime.strptime(date, "%Y-%m-%d").date()
            if d > today or (today - d).days > 14: continue
            if t == "lao":
                if d.weekday() > 4 or not re.fullmatch(r"\d{4}|\d{6}", num): continue
                n += add(db, "lao", date, "main", num[-4:], None, {"six": num} if len(num) == 6 else {}, "gemini")
            elif t == "hanoi":
                low = str(it.get("lower2", "")).strip()
                if not re.fullmatch(r"\d{2}", low): continue
                n += add(db, "hanoi", date, "normal", num, low, {}, "gemini")
        except Exception: continue
    return n

def _gem(prompt):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key: print("GEMINI_API_KEY secret not set"); return []
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]}).encode()
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
    j = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    text = "".join(q.get("text", "") for q in j["candidates"][0]["content"]["parts"])
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else []

def gemini_thai(db):
    """Fallback when the Thai API fails. Same validation, flagged src=gemini."""
    today = datetime.now(timezone.utc).date()
    items = _gem(f"Today is {today}. Use web search to find the ACTUAL official Thai Government Lottery (สลากกินแบ่งรัฐบาล) "
      "results for the last 8 draws. Never guess or invent. Reply with ONLY a JSON array like "
      '[{"type":"thai","date":"2026-11-01","number":"123456","last2":"37","front3":["242","602"],"back3":["239","389"]}]. '
      "number = first prize (6 digits); last2 = 2-digit last; front3/back3 = lists of 3-digit strings. CE dates YYYY-MM-DD; keep leading zeros as strings.")
    n = 0
    for it in items:
        try:
            date, num, l2 = it["date"], str(it["number"]).strip(), str(it["last2"]).strip()
            d = datetime.strptime(date, "%Y-%m-%d").date()
            if d > today or (today - d).days > 200 or not re.fullmatch(r"\d{2}", l2): continue
            f3 = [str(x) for x in it.get("front3", []) if re.fullmatch(r"\d{3}", str(x))][:2]
            b3 = [str(x) for x in it.get("back3", []) if re.fullmatch(r"\d{3}", str(x))][:2]
            n += add(db, "thai", date, "main", num, l2, {"front3": f3, "back3": b3}, "gemini")
        except Exception: continue
    return n

def manual(db):
    p = os.path.join(ROOT, "manual.csv"); n = 0
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8")):
            n += add(db, r["type"].strip(), r["date"].strip(), r.get("variant", "main").strip() or "main",
                     r["number"].strip(), r.get("lower2", "").strip() or None)
    return n

def selftest():
    db = {"draws": []}
    assert add(db, "lao", "2026-11-01", "main", "0707") and db["draws"][0]["number"] == "0707"
    assert not add(db, "lao", "2026-11-01", "main", "1234")          # duplicate
    assert add(db, "hanoi", "2026-11-01", "normal", "0123")          # same day, other type
    assert db["draws"][1]["last2"] == "23" and db["draws"][0]["last2"] == "07"
    assert not add(db, "lao", "01/11/2026", "main", "1111") and not add(db, "lao", "2026-11-02", "main", 7)
    assert add(db, "lao", "2026-11-03", "main", "5521", None, {}, "gemini") and db["draws"][-1]["src"] == "gemini"
    assert lao_from_text({"draws": []}, "19/10/2026 6331 331 31") == 1
    print("selftest OK")

if __name__ == "__main__":
    a = sys.argv
    if "--selftest" in a: selftest(); sys.exit()
    arg = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    db = json.load(open(DATA, encoding="utf-8")); added = {}
    try: added["thai"] = thai(db, arg("--pages", 3), arg("--limit", 40))
    except Exception as e: print("Thai API failed:", type(e).__name__, e); added["thai"] = 0
    if not added.get("thai"):
        try: added["thai_gemini"] = gemini_thai(db)
        except Exception as e: print("Thai Gemini fallback failed:", type(e).__name__, e)
    for u in json.load(open(os.path.join(ROOT, "scripts", "sources.json")))["lao_urls"]:
        try: added["lao"] = added.get("lao", 0) + lao_from_text(db, get(u))
        except Exception as e: print("Lao source failed:", u, e)
    try: added["gemini"] = gemini_fetch(db)
    except Exception as e: print("Gemini fetch failed (data kept):", e)
    added["manual"] = manual(db)
    db["draws"].sort(key=lambda x: (x["type"], x["date"]))
    db["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("added:", added)
