# 出玉ボード

dedama.me（吉兆）の台別成績を GitHub Actions で毎日取得し、GitHub Pages のダッシュボードで見る。

## セットアップ
1. このフォルダの中身を新しいリポジトリ（public でも private でも可）に push する
2. Settings → Actions → General → Workflow permissions を **Read and write** にする
3. Settings → Pages → Source を **Deploy from a branch**、Branch を `main` / `(root)` にする
4. Actions タブ → 「fetch dedama」→ **Run workflow** で1回手動実行して動作確認
5. 数分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` でダッシュボードが見られる

## ファイル
- `fetch_dedama.py` … 取得スクリプト。`data/YYYY-MM-DD.csv` と `data/all.csv` に追記
- `.github/workflows/fetch.yml` … 毎日 00:30 JST に実行（`cron` は UTC 表記）
- `index.html` … ダッシュボード。`data/all.csv` を読んで描画

## メモ
- 実行時刻は閉店後を想定。営業中に実行すると「本日」列が途中経過になるが、翌日の取得で上書きされる
- private リポジトリで Pages を使うには GitHub Pro 以上が必要

## 台移動・撤去・入替について
- 台番号ごとに「その日の機種名」を記録し、前日と機種名が変わった台は入替として扱う
- 台の推移グラフは、今の機種になってからの日数分だけを表示する（旧機種のデータは含めない）
- フロアボードでは、その日に機種が変わった台に黄色い印、ボード下に入替・撤去（データが途切れた台）の一覧
- `today_date` 列はサイト側の「本日」の日付。深夜の実行でサイトの日付切替とずれても正しく並ぶ
