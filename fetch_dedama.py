#!/usr/bin/env python3
"""dedama.me 吉兆 の台別成績を取得して CSV に蓄積するスクリプト。
使い方: python3 fetch_dedama.py [出力ディレクトリ]
毎日1回（例: 22:00 以降）cron 等で実行すると data/YYYY-MM-DD.csv と all.csv が増えていく。
"""
import csv, html, re, sys, time, urllib.request
from datetime import date
from pathlib import Path

BASE = "http://dedama.me/kc_toumei/"
UA = {"User-Agent": "Mozilla/5.0"}
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "data")

def get(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=30).read().decode("cp932", errors="replace")

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

def main():
    OUT.mkdir(parents=True, exist_ok=True)
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
                        "fetch_date": date.today().isoformat(), "today_date": today_date, "site_updated": updated,
                        "kind": kind, "model_id": mid, "model": strip(name), "dai": c[0],
                        "box_d2": c[1], "box_d1": c[2], "box_d0": c[3],
                        "hit_d2": c[4], "hit_d1": c[5], "hit_d0": c[6],
                        "prob_d2": c[7], "prob_d1": c[8], "prob_d0": c[9],
                    })
            time.sleep(0.3)  # サーバーへの負荷配慮
    if not rows:
        sys.exit("データが取れませんでした（サイト構造が変わった可能性）")
    fields = list(rows[0])
    daily = OUT / f"{date.today().isoformat()}.csv"
    with daily.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)
    allf = OUT / "all.csv"
    new = not allf.exists()
    with allf.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fields)
        if new: w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} 台分を {daily} に保存")

if __name__ == "__main__":
    main()
