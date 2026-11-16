#!/usr/bin/env python3
"""ดึง NAV ล่าสุดของกองทุนในพอร์ตจาก SEC Open API (api.sec.or.th) แล้วเขียนลง nav.json

ใช้:  SEC_API_KEY=xxxx python3 scripts/fetch_nav.py
สมัคร key ฟรีได้ที่ SEC Open Data portal (ก.ล.ต.)
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FUNDS = ["EU-US500RMF", "UGQGRMF", "UOBGRMF-H", "TSP3", "TSP5"]
BASE = "https://api.sec.or.th"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nav.json")
LOOKBACK_DAYS = 14

KEYS = [k for k in (os.environ.get("SEC_API_KEY"), os.environ.get("SEC_API_KEY_2")) if k]
if not KEYS:
    sys.exit("ต้องตั้งค่า SEC_API_KEY")


def get(path, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    last_err = None
    for attempt in range(4):
        key = KEYS[attempt % len(KEYS)]
        req = urllib.request.Request(url, headers={
            "Ocp-Apim-Subscription-Key": key,
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 204:
                    return {}
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {url}: {e.read()[:300]!r}"
            if e.code in (401, 403, 404):
                break
        except Exception as e:  # network hiccup
            last_err = f"{e} {url}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last_err)


def items_of(resp):
    if isinstance(resp, list):
        return resp
    for k in ("items", "data", "value"):
        if isinstance(resp.get(k), list):
            return resp[k]
    return []


def norm(s):
    return (s or "").strip().upper()


def load_previous():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def resolve_funds(cached):
    """หา proj_id (และ class) ของแต่ละกองทุน ใช้ค่าที่เคยหาได้ถ้ามี

    ชื่อย่อในพอร์ตอาจเป็นชื่อโครงการ (proj_abbr_name) หรือชื่อ class (fund_class_name
    เช่น UOBGRMF-H) จึงให้ class ที่ตรงเป๊ะชนะ ถ้าไม่มีค่อยใช้ชื่อโครงการ
    """
    found = {c: cached[c] for c in FUNDS if cached.get(c, {}).get("proj_id")}
    want = {norm(c): c for c in FUNDS if c not in found}
    if not want:
        return found
    by_class, by_abbr = {}, {}
    cursor = None
    for _ in range(500):
        params = {"page_size": 500}
        if cursor:
            params["next_cursor"] = cursor
        resp = get("/v2/fund/general-info/profiles", params)
        for it in items_of(resp):
            abbr, cls = norm(it.get("proj_abbr_name")), norm(it.get("fund_class_name"))
            if cls in want:
                by_class.setdefault(cls, it)
            if abbr in want:
                cur = by_abbr.get(abbr)
                if cur is None or (norm(cur.get("fund_class_name")) and not cls):
                    by_abbr[abbr] = it
        if set(want) <= set(by_class):
            break
        cursor = resp.get("next_cursor") if isinstance(resp, dict) else None
        if not cursor:
            break
    for code, orig in want.items():
        it = by_class.get(code) or by_abbr.get(code)
        if it:
            found[orig] = {
                "proj_id": it.get("proj_id"),
                "fund_class_name": it.get("fund_class_name") or "",
                "name_th": it.get("proj_name_th") or "",
                "name_en": it.get("proj_name_en") or "",
            }
    return found


def latest_nav(info):
    today = dt.date.today()
    params = {
        "proj_id": info["proj_id"],
        "start_nav_date": (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat(),
        "end_nav_date": today.isoformat(),
    }
    if info.get("fund_class_name"):
        params["fund_class_name"] = info["fund_class_name"]
    rows = items_of(get("/v2/fund/daily-info/nav", params))
    if info.get("fund_class_name"):
        rows = [r for r in rows if norm(r.get("fund_class_name")) in ("", norm(info["fund_class_name"]))] or rows
    rows = [r for r in rows if r.get("last_val") not in (None, "", 0)]
    if not rows:
        return None
    r = max(rows, key=lambda r: str(r.get("nav_date") or ""))
    return {"nav": float(r["last_val"]), "date": str(r.get("nav_date"))[:10]}


def main():
    prev = load_previous()
    cached = prev.get("funds", {})
    try:
        meta = resolve_funds(cached)
    except Exception as e:
        print("หา proj_id ไม่สำเร็จ:", e, file=sys.stderr)
        meta = {c: v for c, v in cached.items() if v.get("proj_id")}

    funds, ok = {}, 0
    for code in FUNDS:
        entry = dict(cached.get(code, {}))
        if code in meta:
            entry.update({k: v for k, v in meta[code].items() if k in ("proj_id", "fund_class_name", "name_th", "name_en")})
            try:
                res = latest_nav(entry)
                if res:
                    entry.update(res)
                    ok += 1
                    print(f"{code}: {res['nav']} ({res['date']})")
                else:
                    print(f"{code}: ไม่พบ NAV ช่วง {LOOKBACK_DAYS} วันล่าสุด", file=sys.stderr)
            except Exception as e:
                print(f"{code}: ดึง NAV ไม่สำเร็จ: {e}", file=sys.stderr)
        else:
            print(f"{code}: ไม่พบกองทุนนี้ใน SEC API", file=sys.stderr)
        funds[code] = entry

    out = {
        "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).isoformat(timespec="minutes"),
        "source": "SEC Open API (api.sec.or.th)",
        "funds": funds,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if ok == 0:
        sys.exit("ไม่ได้ NAV ของกองทุนใดเลย")


if __name__ == "__main__":
    main()
