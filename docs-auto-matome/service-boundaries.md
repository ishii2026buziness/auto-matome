# Service Boundaries — auto-matome 分割設計

策定日: 2026-03-19

## 現状の責務マップ

| モジュール | 責務 | 外部依存 |
|-----------|------|---------|
| `ingest/` | HN / IndieWeb / Reddit / RSS / X からの記事取得 | HN API, Reddit API, X API, RSS feeds |
| `curate/` | ファクト抽出・トピッククラスタリング・まとめ記事生成 | claude-gateway, NotebookLM |
| `distribution/` | Zenn・X への投稿 | Zenn git repo, X API |
| `analytics/` | トラフィック取得・エンゲージメントレポート | Plausible API |
| `orchestrator/` | パイプライン全体のスケジューリング・ハートビート | — |
| `common/` | 設定・メトリクス・閾値（共有ユーティリティ） | — |

## 候補サービス

### svc-ingest（第1候補）
- `ingest/` 全体をそのまま切り出す
- 入力: なし（スケジュール起動）
- 出力: 記事 JSON リスト（ファイル or キュー）
- 外部認証: Reddit / X API キーのみ保有
- **分離コストが最小**: 他モジュールへの依存がなく、I/O 境界が明確

### svc-curate
- `curate/` を切り出し
- 入力: 記事 JSON リスト
- 出力: まとめ Markdown
- 外部依存: claude-gateway（HTTP）, NotebookLM API
- gateway 移行が完了しているため次に分離しやすい

### svc-distribute
- `distribution/` を切り出し
- 入力: まとめ Markdown
- 出力: Zenn / X への投稿
- 独立性が高いが投稿先の認証管理が必要

### svc-analytics
- `analytics/` を切り出し
- 完全に読み取り専用・他サービスと非同期で動いてよい
- 優先度低

## 抽出順序の提案

1. **svc-ingest** — 依存関係なし、境界が明確、最初の extraction に最適
2. **svc-curate** — gateway 移行済みでほぼ準備完了
3. **svc-distribute** — 投稿先認証の整理が必要
4. **svc-analytics** — 最後、優先度低

## 第1抽出ターゲット: svc-ingest

`ingest/` ディレクトリを service-template ベースの独立リポジトリへ切り出す。
KEN-42 で実施。
