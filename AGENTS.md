# AGENTS.md — Auto Matome

## デプロイ方針（ADR-0004）

このサービスは **uv2nix + NixOS container（systemd-nspawn）** でK12にデプロイされる。

- Podman/Containerfile/GHCRへのpushは**不要**（廃止済み）
- K12へのデプロイ設定は `k12-network-notes` リポジトリの `nixos/modules/auto-matome.nix` で管理
- このサービスは `claude -p` を呼ぶため NixOS container で隔離される（プロンプトインジェクション対策）
- K12上での役割: コンテンツ生成のみ。site build/deploy は GitHub Actions (ubuntu-latest) が担当
- 生成コンテンツは `content-data` ブランチに push → GitHub Actions がトリガーされ Cloudflare にデプロイ

This repository is an autonomous Japanese-language curation media that collects trending tech and social news from Hacker News and IndieWeb RSS feeds, converts them into 2ch-style matome articles, and publishes daily to an Astro SSG site on Cloudflare Pages.

## Purpose

- Collect daily trending articles from Hacker News (top stories) and IndieWeb RSS feeds (9 feeds)
- Convert collected content into 2ch-style Japanese matome articles via Claude Code subagents
- Automatically build and deploy to https://auto-matome.pages.dev/ via Cloudflare Pages
- Drive traffic via X auto-posting (not yet implemented — X API key required)

## Working Loop

Every task follows this loop. Do not skip steps.

1. **Assess** — Read `progress/current.md`. Check pipeline status and KPIs.
2. **Advance** — Pick one incomplete item. Make the smallest meaningful change.
3. **Tidy** — Clean up formatting, naming, and documentation touched by the change.
4. **Verify** — Run `./tools/harness self-check`. Fix any failures before proceeding.
5. **Record** — Update `progress/current.md` (Last Session, Next Actions, Blockers, Risks).

## Working Rules

- Read this file before starting substantial work.
- Follow the Working Loop for every task.
- Put durable decisions and research outcomes in `docs/`.
- Put current status and next actions in `progress/current.md`.
- All translations must include source URL attribution (zero tolerance for missing citations).
- Quality is judged by numeric thresholds only. Never ask a human to review.
- Use local GPU (RTX 5060Ti) for embeddings and trend clustering when possible.
- On 3 consecutive API errors, auto-halt and issue re-auth task.

## Pipeline Architecture

```
[HN Firebase API] ──┐
                     ├→ [Dedup + Quality Gate] → [output/YYYY-MM-DD.md] → [Claude subagent: 2ch化] → [Astro Build] → [CF Pages Deploy]
[IndieWeb RSS x9] ──┘
```

**実装済み（動作中）**: HN収集、IndieWeb RSS収集、dedup、quality gate、Astro build、CF Pages deploy

**未実装（スタブ）**: Reddit収集、X収集、LLM翻訳、LLM要約、X自動投稿

**2ch化の現状**: pipeline.pyは英語リンク集を出力するのみ。2ch風まとめへの変換はClaudeサブエージェントによる手動実行で対応中。pipeline.pyへの統合は未完了。

## Tech Stack

- Astro (SSG), Python 3.12, uv
- HN Firebase API（認証不要）, IndieWeb RSS（9フィード固定）
- Claude Code subagents（2ch風変換）
- Cloudflare Pages（wrangler、OAuth認証済み）
- Podman + systemd/Quadlet for runtime execution; OpenClaw remains a future higher-level orchestrator

## Blockers

A blocker is an obstacle the agent cannot resolve on its own:

- Permission or access restrictions
- API quota exhaustion
- Reddit/HN rate limiting
- Budget limit reached

When a blocker is detected:

1. Stop work on the blocked task immediately.
2. Document the blocker in `progress/current.md`.
3. Notify via OpenClaw message channel.
4. Move to other unblocked tasks.

## Definition of Done

A task is done only when all of the following are true:

- The requested change is implemented or the blocker is clearly documented.
- Relevant decisions are recorded in `docs/`.
- `progress/current.md` is updated.
- `./tools/harness self-check` has passed.
- Daily pipeline produces >= 3 Japanese articles from overseas sources.
