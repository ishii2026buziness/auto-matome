# Auto Matome 改修計画 — 著作権リスク低減 + 独自解釈記事化

策定日: 2026-03-12
策定: Claude + Codex

## 方針

- **著作権リスク低減**（P0）: 画像直埋め込み廃止、原文文章の借用をやめる
- **コンテンツ品質向上**（P1）: 多ソース→事実抽出→独自解釈・トレンド予測記事に再構成
- **ソース拡充**（P2）: 現在5件 → 20件目標
- フロント（2ch風Astro）・インフラ（CF Pages・cron・X投稿）は変更しない

## パイプライン変更イメージ

```
【変更前】
fetch → dedup → Claude「2ch風に変換」（原文ほぼそのまま） → 公開

【変更後】
fetch(20ソース) → dedup → fact_extractor（事実/数値/争点/世論を構造化）
  → topic_cluster（類似話題を統合）
  → article_brief（何が起きた/なぜ話題/賛否/今後）
  → Claude「独自解釈2ch風記事として再構成」 → 公開
```

## タスク分解

### P0: 著作権リスク低減（先に入れる）

| # | タスク | 変更ファイル | 内容 |
|---|--------|-------------|------|
| 1 | 禁止事項文書化 | `docs/execution-plan.md` | 「画像直埋め込み禁止」「原文引用禁止」「要約は構造化後のみ」を明文化 |
| 2 | 構造化スキーマ定義 | 新規 `src/curate/evidence_schema.py` | `facts[]`, `numbers[]`, `sentiment[]`, `predictions[]`, `source_urls[]` の中間スキーマ |
| 3 | Reddit画像直埋め込み停止 | `src/ingest/fetch_reddit.py`, `src/curate/matome_converter.py` | `image_url` を公開用に使わない。URL・ドメイン・メタデータのみ残す |
| 4 | テキストリンクカード追加 | 新規 `src/curate/link_card.py` | 画像なしリンクカード生成。表示: `媒体名 / タイトル / 1-2行説明 / URL` |
| 5 | Claude入力から原文除去 | `src/curate/matome_converter.py` | title/summary/commentの生文を直接渡すのをやめ、構造化済み論点のみ渡す |

### P1: 2ステップ化と独自解釈記事化

| # | タスク | 変更ファイル | 内容 |
|---|--------|-------------|------|
| 6 | 事実抽出ステップ追加 | 新規 `src/curate/fact_extractor.py`, `src/pipeline.py` | sourceごとに `事実・数値・争点・世論` を抽出し evidence 化 |
| 7 | トピック統合ステップ追加 | 新規 `src/curate/topic_cluster.py`, 既存 `src/curate/trend_detector.py` | 類似話題を束ね、1記事=1トピックに再編成 |
| 8 | 記事ブリーフ生成 | 新規 `src/curate/article_brief_builder.py` | トピックごとに `何が起きた/なぜ話題/賛否/今後` を組み立て |
| 9 | Claudeプロンプト変更 | `src/curate/matome_converter.py` | 「変換」→「多ソース統合・独自解釈・予測付き2ch風記事として再構成」に変更 |
| 10 | パイプライン2ステップ化 | `src/pipeline.py` | `extract_facts() → cluster_topics() → build_briefs() → convert_to_matome()` の流れに変更 |

### P2: ソース20件化

| # | タスク | 変更ファイル | 内容 |
|---|--------|-------------|------|
| 11 | RSS 20件化と重み付け | `config/sources.yaml`, `src/ingest/fetch_rss.py` | feedごとに `label/category/priority/max_items` を持たせる |
| 12 | テスト追加 | 新規 `tests/test_fact_extractor.py` 等 | 著作権リスク回避・カード生成・クラスタ統合の回帰防止 |
| 13 | 進捗文書更新 | `progress.md`, `progress/current.md` | 改修完了条件と残課題を更新 |

## Claude新プロンプト要件

### 必須
- 3ソース以上を統合して1トピック化
- 事実と憶測を分離して書く
- Redditコメントはそのまま借用せず要約
- 最後に「今後ありそうな展開」を1段落

### 禁止
- 原文の言い回し踏襲
- 逐語的な引用
- 画像埋め込み
- 見出しの原題直訳・近似

## Step A/B の入出力仕様

### Step A: fact_extractor
- **入力**: title, summary, score, comments, published, source
- **出力**: `verified_facts`, `numbers`, `arguments_for`, `arguments_against`, `public_reaction`, `unknowns`

### Step B: matome_converter（Claude）
- **入力**: topicごとの article_brief（facts + brief構造体）
- **出力**: 2ch風の読み物記事

## RSSソース候補20件

先に入れるべき12件（推奨）:

| 区分 | ソース | URL |
|------|--------|-----|
| AI | OpenAI News | `https://openai.com/news/rss.xml` |
| AI | Anthropic News | `https://www.anthropic.com/news/rss.xml` |
| AI | Google AI Blog | `https://blog.google/technology/ai/rss/` |
| AI | Hugging Face Blog | `https://huggingface.co/blog/feed.xml` |
| AI | LangChain Blog | `https://blog.langchain.com/rss/` |
| AI | Simon Willison | `https://simonwillison.net/atom/everything/` |
| Tech | Ars Technica | `https://feeds.arstechnica.com/arstechnica/index` |
| Tech | The Verge | `https://www.theverge.com/rss/index.xml` |
| Tech | TechCrunch | `https://techcrunch.com/feed/` |
| Tech | VentureBeat | `http://feeds.venturebeat.com/topstories` |
| Tech | Cloudflare Blog | `https://blog.cloudflare.com/rss/` |
| Tech | GitHub Blog | `https://github.blog/feed/` |

追加候補8件:

| 区分 | ソース | URL |
|------|--------|-----|
| AI | Import AI | `https://importai.substack.com/feed` |
| AI | IEEE Spectrum AI | `https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss` |
| Tech | Ars Technica AI | `https://arstechnica.com/ai/feed/` |
| Tech | MIT Technology Review | `https://www.technologyreview.com/feed` |
| Tech | The New Stack | `https://thenewstack.io/blog/feed/` |
| Tech | Tailscale Blog | `https://tailscale.com/blog/index.xml` |
| Tech | InfoQ | `https://feed.infoq.com` |
| Tech | TLDR Tech | `https://tldr.tech/api/rss/tech` |

## 変更後の出力イメージ

**変更前:**
- 単記事ベース、Reddit画像直埋め込み、元文脈を引きずった2ch化

**変更後:**
- 1テーマ = 複数ソース統合
- 画像なしリンクカード（媒体名/タイトル/説明/URL）
- 「事実」「世論」「予測」を分けた再構成記事
- 2ch風の見た目は維持、実体はニュース分析記事
