# Auto Matome — 実行計画

## 技術スタック

- フロント: Astro (SSG, 多言語ページ)
- 収集: Reddit API, Hacker News Firebase API, RSS, X API
- 翻訳/要約: Gemini 2.x or Claude (日英変換)
- トレンド検出: sentence-transformers (ローカルGPU), scikit-learn
- 配信: X API, Zenn CLI (記事転送)
- 分析: Plausible or GA4
- 実行: Podman + systemd/Quadlet（将来 OpenClaw が上位から実行判断）
- ストレージ: SQLite (初期) + DuckDB (トレンド集計)

## ディレクトリ構成

```
packages/auto-matome/src/
  common/
    config.py
    metrics.py
    thresholds.py
  ingest/
    fetch_indieweb.py
    fetch_reddit.py
    fetch_hn.py
    fetch_x.py
  curate/
    translate_ja.py
    summarize.py
    tagger.py
    trend_detector.py
    quality_gate.py
  site/
    astro_writer.ts
    build_deploy.ts
  distribution/
    post_x.py
    post_zenn.py
  analytics/
    traffic_pull.py
    engagement_report.py
  orchestrator/
    heartbeat_tasks.py  # legacy threshold-check helper, not runtime control
```

## 実装タスク (各2時間以内)

| # | タスク | 依存 |
|---|--------|------|
| 1 | 情報源コネクタ雛形作成 (IndieWeb/Reddit/HN/X) | - |
| 2 | 各API認証と取得テスト | 1 |
| 3 | 正規化スキーマ実装 | 2 |
| 4 | 翻訳パイプライン実装 | 3 |
| 5 | 要約/分類実装 | 4 |
| 6 | トレンドクラスタリング実装 | 5 |
| 7 | 品質ゲート (翻訳品質・重複・出典明記) | 6 |
| 8 | Astro 記事出力実装 | 7 |
| 9 | 自動デプロイ実装 | 8 |
| 10 | X 投稿実装 | 9 |
| 11 | Zenn 投稿実装 | 9 |
| 12 | 分析取得実装 | 10, 11 |
| 13 | 改善ループ (話題重み更新) | 12 |
| 14 | Heartbeat 統合 | 13 |
| 15 | E2E (収集→公開→配信) 試験 | 14 |

依存関係: 1→2→3→4→5→6→7→8→9→10,11→12→13→14→15
(タスク10と11は並行実行可能、タスク12で合流)

## HEARTBEAT.md 定常チェック項目

```markdown
# Auto Matome Heartbeat

- [ ] 新規海外ソース取得 >= 30件/日
- [ ] 日本語公開本数 >= 3件/日
- [ ] 翻訳品質スコア >= 0.80 (LLM自己評価)
- [ ] 出典URL欠損 = 0
- [ ] 重複公開率 <= 5%
- [ ] 日次コスト <= 3,000円
- [ ] 7日移動PV成長率 < -15% なら自動で話題配分変更
- [ ] 投稿先APIエラー連続3回で自動停止/再認証タスク発行
```

## 初日にAIだけで完了可能なタスク

- 主要4ソース接続
- 翻訳・要約・タグ付け自動化
- Astroページ自動生成
- X または Zenn 片系自動投稿
- 初期トレンドレポート生成
- Heartbeat閾値ルール作成
