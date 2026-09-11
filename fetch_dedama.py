#!/usr/bin/env python3
"""dedama.me 吉兆 の台別成績を取得して CSV に蓄積するスクリプト。
使い方: python3 fetch_dedama.py [出力ディレクトリ]
毎日1回（例: 22:00 以降）cron 等で実行すると data/YYYY-MM-DD.csv と all.csv が増えていく。
"""
import csv, html, re, sys, time, urllib.request
from datetime import date
from pathlib import Path

# 取得する店舗（URLのフォルダ名: 表示名）。増やしたいときはここに足す
STORES = {
    "kc_toumei": "東名",
    "kc_nogawa": "野川",
}
UA = {"User-Agent": "Mozilla/5.0"}
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data")

def get(url, retries=5):
    """503 などで失敗したら待ってやり直す（最大 retries 回、待ち時間は 30s → 60s → 120s …）"""
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return urllib.request.urlopen(req, timeout=30).read().decode("cp932", errors="replace")
        except Exception as e:
            if i == retries - 1:
                raise
            wait = 30 * 2 ** i
            print(f"  取得失敗 ({e}) {wait}秒待って再試行", flush=True)
            time.sleep(wait)

def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\xa0", " ").strip()

def site_today(dom):
    """「本日」の日(dom)から実際の日付を返す。実行日と前後1日以内で一致する日を採用"""
    from datetime import timedelta
    for off in (0, -1, 1):
        d = date.today() + timedelta(days=off)
        if d.day == dom:
            return d.isoformat()
    return ""

def fetch_store(code, store_name):
    BASE = f"http://dedama.me/{code}/"
    top = get(BASE)
    sid = re.search(r"s=([0-9a-f]+)", top).group(1)   # セッションIDは毎回変わる
    rows = []
    for ps, kind in (("P", "パチンコ"), ("S", "スロット")):
        lst = get(f"{BASE}choice_mc.html?s={sid}&ps={ps}")
        updated = re.search(r"\((\d+/\d+ \d+:\d+) 更新\)", lst)
        updated = updated.group(1) if updated else ""
        models = re.findall(r'href="choice_no_of_mc\.html\?s=\w+&ps=\w&m=(\d+)"[^>]*>(.*?)</a>', lst, re.S)
        for mid, name in models:
            page = get(f"{BASE}choice_no_of_mc.html?s={sid}&ps={ps}&m={mid}")
            # 見出しの「本日10 木」から、サイト側の「本日」の日付を確定させる（深夜実行で日付がずれても正しく残す）
            m_today = re.search(r"本日(?:<br>|\s|\xa0)*(\d+)", page)
            today_date = site_today(int(m_today.group(1))) if m_today else ""
            for tr in re.findall(r"<tr.*?</tr>", page, re.S):
                c = [strip(x) for x in re.findall(r"<t[dh].*?</t[dh]>", tr, re.S)]
                if len(c) == 10 and re.fullmatch(r"\d+", c[0]):
                    rows.append({
                        "store": store_name, "fetch_date": date.today().isoformat(), "today_date": today_date, "site_updated": updated,
                        "kind": kind, "model_id": mid, "model": strip(name), "dai": c[0],
                        "box_d2": c[1], "box_d1": c[2], "box_d0": c[3],
                        "hit_d2": c[4], "hit_d1": c[5], "hit_d0": c[6],
                        "prob_d2": c[7], "prob_d1": c[8], "prob_d0": c[9],
                    })
            time.sleep(1.0)  # 1秒に1ページまで（サーバーへの負荷配慮）
        print(f"  {store_name} {kind}: {len(models)} 機種", flush=True)
    return rows

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for code, name in STORES.items():
        try:
            got = fetch_store(code, name)
            print(f"{name}: {len(got)} 台", flush=True)
            rows += got
        except Exception as e:
            print(f"{name}: 取得失敗 {e}")
    if not rows:
        sys.exit("データが取れませんでした（サイト構造が変わった可能性）")
    fields = list(rows[0])

    # 旧形式（all.csv / 日別csv）が残っていれば月別に振り分けて片付ける
    migrate_old_files(fields)

    # 月別ファイル（data/YYYY-MM.csv）に保存。同じ取得日の行がすでにあれば置き換える（再実行対策）
    by_month = {}
    for r in rows:
        by_month.setdefault(month_of(r), []).append(r)
    for month, mrows in by_month.items():
        write_month(month, mrows, fields)
    write_index()
    print(f"{len(rows)} 台分を保存: " + ", ".join(f"{m}.csv" for m in sorted(by_month)))

def month_of(r):
    return (r.get("today_date") or r["fetch_date"])[:7]

def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def write_month(month, new_rows, fields):
    """月ファイルに追記。同じ fetch_date の既存行は捨てて新しい行で置き換える"""
    path = OUT / f"{month}.csv"
    old = [r for r in read_csv(path) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("fetch_date") or "")] if path.exists() else []
    dates = {r["fetch_date"] for r in new_rows}
    old = [r for r in old if r.get("fetch_date") not in dates]
    for r in old:
        for k in fields:
            r.setdefault(k, "")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore"); w.writeheader()
        w.writerows(old); w.writerows(new_rows)

def migrate_old_files(fields):
    first_store = next(iter(STORES.values()))
    allf = OUT / "all.csv"
    if allf.exists():
        old = [r for r in read_csv(allf) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.get("fetch_date") or "")]  # 列ずれで壊れた行は捨てる
        by_month = {}
        for r in old:
            for k in fields:
                r.setdefault(k, "")
            r["store"] = r["store"] or first_store
            by_month.setdefault(month_of(r), []).append(r)
        for month, mrows in by_month.items():
            write_month(month, mrows, fields)
        allf.unlink()
        print(f"all.csv を月別に分割しました: {', '.join(sorted(by_month))}")
    for p in OUT.glob("????-??-??.csv"):   # 日別ファイルは月別に含まれるので削除
        p.unlink()

def write_index():
    """ダッシュボードが読む月の一覧（新しい順）"""
    import json
    months = sorted((p.stem for p in OUT.glob("????-??.csv")), reverse=True)
    (OUT / "index.json").write_text(json.dumps({"months": months}, ensure_ascii=False))

if __name__ == "__main__":
    main()
