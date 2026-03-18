# Bootstrap

このファイルが存在する = 未セットアップ。
セットアップ完了後にこのファイルを削除すること。

## ヒアリング方法

ユーザーへの質問はインタラクティブなツールを使うこと：

- **Claude Code** — `AskUserQuestion` ツールを使う（選択肢を提示してユーザーが選べる）
- **その他のエージェント** — 同等のインタラクティブUIツールがあれば使う。なければ1問ずつ質問して回答を待つ

## 手順

### 1. サービス名を設定

`service.config.yaml` を作成：

```yaml
service_name: <サービス名をここに記入>
infra:
  url: https://github.com/ishii2025buziness/k12-network-notes  # デフォルト。変える場合はここを書き換える
  type: k12
```

### 2. infra submoduleを追加

デフォルト（k12-network-notes）の場合：

```bash
git submodule add https://github.com/ishii2025buziness/k12-network-notes infra
git submodule update --init --recursive
```

別のインフラを使う場合は `service.config.yaml` の `infra.url` を変更してから上記コマンドのURLを差し替える。

### 3. infraのデータパスを確認する

`infra/` のマウント定義を読み、コンテナの `/data` がホストのどこにマウントされるかを確認する。
`app/src/pipeline.py` の `ArtifactStore` の `root_dir` をそのパスに合わせること。

### 4. app/pyproject.tomlのservice_nameを更新

`app/pyproject.toml` の `name = "service-name"` を実際のサービス名に変更。

### 5. app/src/pipeline.py のpipeline名を更新

`pipeline="service-name"` を実際のサービス名に変更。

### 6. このファイルを削除

```bash
git rm BOOTSTRAP.md
git commit -m "bootstrap: initialize <サービス名>"
```
