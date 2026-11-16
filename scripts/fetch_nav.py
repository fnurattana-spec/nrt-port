#!/usr/bin/env python3
"""ดึง NAV ล่าสุดของกองทุนในพอร์ตแล้วเขียนลง nav.json

แหล่งข้อมูล
- ค่าเริ่มต้น: Finnomena (ไม่ต้องใช้ key; เป็น API ที่ไม่ได้เปิดอย่างเป็นทางการ อาจเปลี่ยนได้)
- ถ้าตั้ง SEC_API_KEY ไว้: ใช้ SEC Open API (api.sec.or.th) ของ ก.ล.ต. ก่อน
  กองไหนดึงไม่ได้จะลองอีกแหล่งให้อัตโนมัติ

ใช้:  python3 scripts/fetch_nav.py
"""
import datetime as dt
import difflib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FUNDS = ["EU-US500RMF", "UGQGRMF", "UOBGRMF-H", "TSP3", "TSP5"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nav.json")
LOOKBACK_DAYS = 14
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TZ_TH = dt.timezone(dt.timedelta(hours=7))

SEC_KEYS = [k for k in (os.environ.get("SEC_API_KEY"), os.environ.get("SEC_API_KEY_2")) if k]


def log(*a):
    print(*a, file=sys.stderr)


def norm(s):
    return (s or "").strip().upper()


def http_json(url, headers=None, tries=3):
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            **(headers or {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                if r.status == 204:
                    return {}
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {url}: {e.read()[:200]!r}"
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            last = f"{type(e).__name__}: {e} {url}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last)


def list_in(obj, *keys):
    """หา list ข้างใน response ที่หน้าตาไม่แน่นอน"""
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        return []
    for k in keys:
        v = obj.get(k)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            inner = list_in(v, *keys)
            if inner:
                return inner
    return []


def iso_date(v):
    return str(v or "")[:10]


# ---------------------------------------------------------------- Finnomena
FN = "https://www.finnomena.com/fn3/api/fund"
# ชื่อย่อในพอร์ต → ชื่อย่อที่ Finnomena ใช้ (ใส่เฉพาะกองที่ชื่อไม่ตรงกัน)
FN_ALIASES = {
    "EU-US500RMF": "ES-US500RMF",
}
# คำค้นในชื่อกอง (ไทย/อังกฤษ) ไว้ช่วยหาในล็อกเมื่อชื่อย่อไม่ตรง
FN_NAME_HINTS = {
    "TSP3": ["SMART PORT 3", "SMARTPORT 3", "สมาร์ท พอร์ต 3", "สมาร์ทพอร์ต 3", "BALANCER"],
    "TSP5": ["SMART PORT 5", "SMARTPORT 5", "สมาร์ท พอร์ต 5", "สมาร์ทพอร์ต 5", "GO-GETTER", "GOGETTER"],
}
FN_LISTS = [
    FN + "/public/list",
    FN + "/v2/public/funds",
    FN + "/public/filter/overview",
]


def fn_resolve(want):
    """หา id ของกองทุนใน Finnomena จากชื่อย่อ (short_code)"""
    want = {norm(FN_ALIASES.get(orig, orig)): orig for orig in want.values()}
    found, all_codes, named = {}, set(), []
    for url in FN_LISTS:
        try:
            rows = list_in(http_json(url), "data", "funds", "items", "result")
        except Exception as e:
            log("Finnomena list:", e)
            continue
        for it in rows:
            if not isinstance(it, dict):
                continue
            code = norm(it.get("short_code") or it.get("shortCode") or it.get("code") or it.get("fund_code"))
            fid = it.get("id") or it.get("fund_id") or it.get("fundId")
            if code:
                all_codes.add(code)
                named.append((code, str(fid), f"{it.get('name_th') or ''} {it.get('name_en') or ''}".strip()))
            if code in want and fid and want[code] not in found:
                found[want[code]] = {
                    "fn_id": str(fid),
                    "name_th": it.get("name_th") or it.get("nameTh") or "",
                    "name_en": it.get("name_en") or it.get("nameEn") or "",
                }
        if len(found) == len(want):
            break
    for code, orig in want.items():
        if orig not in found and orig in FN_NAME_HINTS:
            hints = [h.upper() for h in FN_NAME_HINTS[orig]]
            for c, i, n in named:
                if any(h in n.upper() or h in c for h in hints):
                    log(f"[finnomena] {orig}: ชื่อตรงคำค้น → {c} ({i}) {n}")
        if orig not in found and all_codes:
            log(f"[finnomena] {orig}: ชื่อที่ใกล้เคียง → {', '.join(suggest(code, all_codes)) or '-'}")
    return found


def suggest(code, codes, n=12):
    """ชื่อกองที่หน้าตาคล้าย code เพื่อช่วยหาชื่อย่อที่ถูกต้อง"""
    core = code.replace("RMF", "").replace("SSF", "").strip("-")
    parts = [p for p in core.replace("-", " ").split() if len(p) >= 3]
    hits = [c for c in codes if any(p in c for p in parts) or core in c]
    hits = sorted(hits, key=lambda c: (-difflib.SequenceMatcher(None, code, c).ratio(), c))
    close = difflib.get_close_matches(code, list(codes), n=n, cutoff=0.5)
    out = []
    for c in close + hits:
        if c not in out:
            out.append(c)
    return out[:n]


def fn_latest(info):
    fid = urllib.parse.quote(info["fn_id"])
    urls = [
        f"{FN}/v2/public/funds/{fid}/nav/q?range=1M",
        f"{FN}/nav/q?fund={fid}&range=1M",
    ]
    for url in urls:
        try:
            rows = list_in(http_json(url), "data", "navs", "nav")
        except Exception as e:
            log("Finnomena nav:", e)
            continue
        rows = [r for r in rows if isinstance(r, dict) and r.get("value") not in (None, "", 0)]
        if rows:
            r = max(rows, key=lambda r: str(r.get("date") or r.get("nav_date") or ""))
            return {"nav": float(r["value"]), "date": iso_date(r.get("date") or r.get("nav_date"))}
    return None


# ---------------------------------------------------------------- SEC Open API
SEC = "https://api.sec.or.th"


def sec_get(path, params):
    last = None
    for key in SEC_KEYS:
        try:
            return http_json(SEC + path + "?" + urllib.parse.urlencode(params),
                             {"Ocp-Apim-Subscription-Key": key, "Cache-Control": "no-cache"})
        except Exception as e:
            last = e
    raise last


def sec_resolve(want):
    """ชื่อย่อในพอร์ตอาจเป็นชื่อโครงการ (proj_abbr_name) หรือชื่อ class (เช่น UOBGRMF-H)
    ให้ class ที่ตรงเป๊ะชนะ ถ้าไม่มีค่อยใช้ชื่อโครงการ"""
    by_class, by_abbr, cursor = {}, {}, None
    for _ in range(500):
        params = {"page_size": 500}
        if cursor:
            params["next_cursor"] = cursor
        resp = sec_get("/v2/fund/general-info/profiles", params)
        for it in list_in(resp, "items", "data", "value"):
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
    found = {}
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


def sec_latest(info):
    today = dt.datetime.now(TZ_TH).date()
    params = {
        "proj_id": info["proj_id"],
        "start_nav_date": (today - dt.timedelta(days=LOOKBACK_DAYS)).isoformat(),
        "end_nav_date": today.isoformat(),
    }
    if info.get("fund_class_name"):
        params["fund_class_name"] = info["fund_class_name"]
    rows = list_in(sec_get("/v2/fund/daily-info/nav", params), "items", "data", "value")
    if info.get("fund_class_name"):
        rows = [r for r in rows if norm(r.get("fund_class_name")) in ("", norm(info["fund_class_name"]))] or rows
    rows = [r for r in rows if r.get("last_val") not in (None, "", 0)]
    if not rows:
        return None
    r = max(rows, key=lambda r: str(r.get("nav_date") or ""))
    return {"nav": float(r["last_val"]), "date": iso_date(r.get("nav_date"))}


# ---------------------------------------------------------------- main
SOURCES = [  # (ชื่อ, field ที่บอกว่าหาเจอแล้ว, resolve, latest)
    ("sec", "proj_id", sec_resolve, sec_latest),
    ("finnomena", "fn_id", fn_resolve, fn_latest),
]


def main():
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        prev = {}
    funds = {c: dict(prev.get("funds", {}).get(c, {})) for c in FUNDS}
    done = set()

    for name, id_field, resolve, latest in SOURCES:
        if name == "sec" and not SEC_KEYS:
            continue
        todo = [c for c in FUNDS if c not in done]
        if not todo:
            break
        want = {norm(c): c for c in todo if not funds[c].get(id_field)}
        if want:
            try:
                for code, meta in resolve(want).items():
                    funds[code].update({k: v for k, v in meta.items() if v or k not in funds[code]})
            except Exception as e:
                log(f"[{name}] หารหัสกองทุนไม่สำเร็จ: {e}")
        for code in todo:
            if not funds[code].get(id_field):
                log(f"[{name}] {code}: ไม่พบกองทุนนี้")
                continue
            try:
                res = latest(funds[code])
            except Exception as e:
                log(f"[{name}] {code}: ดึง NAV ไม่สำเร็จ: {e}")
                continue
            if res:
                funds[code].update(res, source=name)
                done.add(code)
                print(f"[{name}] {code}: {res['nav']} ({res['date']})")
            else:
                log(f"[{name}] {code}: ไม่พบ NAV ล่าสุด")

    out = {
        "updated": dt.datetime.now(TZ_TH).isoformat(timespec="minutes"),
        "funds": funds,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    missing = [c for c in FUNDS if c not in done]
    if missing:
        log("รอบนี้ไม่ได้ NAV:", ", ".join(missing))
    if not done:
        sys.exit("ไม่ได้ NAV ของกองทุนใดเลย")


if __name__ == "__main__":
    main()
