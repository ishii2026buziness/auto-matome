# デプロイ方針 — Auto Matome

## デプロイ先

**K12 NixOS (uv2nix + NixOS container / systemd-nspawn)**

## 概要

- このサービスは `claude -p` を呼ぶため、**NixOS container（systemd-nspawn）による隔離が必須**（プロンプトインジェクション対策）
- Podman/Containerfile/GHCRへのpushは不要（廃止済み）

## K12上での役割とデプロイフロー

- **K12の役割: コンテンツ生成のみ**（`AUTO_MATOME_SKIP_SITE_BUILD=1` を設定）
- site build / wrangler deploy は **GitHub Actions (ubuntu-latest)** が担当
- コンテンツ生成後は `content-data` ブランチに push → GitHub Actions がトリガーされ Cloudflare Pages にデプロイ

## 環境変数

| 変数 | 用途 |
|------|------|
| `AUTO_MATOME_SKIP_SITE_BUILD=1` | K12上でsite buildをスキップ |
| `AUTO_MATOME_PUSH_CONTENT=1` | コンテンツ生成後にgit pushを有効化 |
| `GITHUB_TOKEN` | `AUTO_MATOME_PUSH_CONTENT=1` と組み合わせてgit pushに使用 |

## k12-network-notes 管理ファイル

- `nixos/modules/auto-matome.nix` — systemd-nspawn container設定
- `nixos/packages/auto-matome.nix` — uv2nixパッケージ定義

## 廃止済み

- Podman/Containerfile/GHCR（ADR-0004により廃止）
