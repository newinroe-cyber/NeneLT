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

def add(db, t, date, variant, number, last2=None, extra=None):
    number = str(number).strip()
    if t not in LEN or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date): return False
    try: datetime.strptime(date, "%Y-%m-%d")
    except ValueError: return False
    if not (number.isdigit() and len(number) == LEN[t]): return False
    if any(x["type"] == t and x["date"] == date and x.get("variant") == variant for x in db["draws"]): return False
    db["draws"].append({"type": t, "date": date, "variant": variant, "number": number,
                        "last2": last2 or number[-2:], "extra": extra or {}})
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
    assert lao_from_text({"draws": []}, "19/10/2026 6331 331 31") == 1
    print("selftest OK")

if __name__ == "__main__":
    a = sys.argv
    if "--selftest" in a: selftest(); sys.exit()
    arg = lambda k, d: int(a[a.index(k) + 1]) if k in a else d
    db = json.load(open(DATA, encoding="utf-8")); added = {}
    try: added["thai"] = thai(db, arg("--pages", 3), arg("--limit", 40))
    except Exception as e: print("Thai update failed (data kept):", e)
    for u in json.load(open(os.path.join(ROOT, "scripts", "sources.json")))["lao_urls"]:
        try: added["lao"] = added.get("lao", 0) + lao_from_text(db, get(u))
        except Exception as e: print("Lao source failed:", u, e)
    added["manual"] = manual(db)
    db["draws"].sort(key=lambda x: (x["type"], x["date"]))
    db["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(db, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("added:", added)
