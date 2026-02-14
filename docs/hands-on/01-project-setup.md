# Hands-on 01: プロジェクト基盤の構築

本ハンズオンの第一歩として、AWS CDKを用いたPythonプロジェクトの初期化を行い、ドメイン駆動設計 (DDD) に適したディレクトリ構造をセットアップします。

## 1. 目的
*   **モダンな開発環境の構築**: 従来の `pip` + `venv` ではなく、高速かつ統合的なパッケージマネージャーである **uv** を採用し、再現性の高い開発環境を構築します。
*   AWS CDK (Python) の開発環境を整える。
*   将来的な拡張（マイクロサービス化）に備えた、明確なレイヤー構造を作成する。

## 2. 前提条件 (Prerequisites)
以下のツールがインストールされていることを確認してください。

*   **uv**: `uv --version` (最新のPythonパッケージマネージャー)
    *   インストール: `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux)
*   **Python 3.14**: `uv python install 3.14` (uv経由で管理します)
*   **Node.js 18 以上**: `node --version`
*   **AWS CLI**: `aws --version` (かつ `aws configure` で認証情報が設定済みであること)
*   **AWS CDK CLI**: `cdk --version`
    *   未インストールの場合: `npm install -g aws-cdk`

## 3. CDKプロジェクトの初期化

まず、プロジェクトのルートディレクトリを作成し、CDKアプリケーションを初期化します。

```bash
# プロジェクトディレクトリの作成（もし存在しない場合）
# mkdir serverless-trip-saga-python
# cd serverless-trip-saga-python

# CDK Pythonプロジェクトの初期化
# --language python: Python用のテンプレートを使用
cdk init app --language python

# 不要なファイルの削除 (Windows用のバッチファイルなど)
rm source.bat
```

実行後、`app.py` や `cdk.json` などが生成されていることを確認します。

## 4. 仮想環境と依存ライブラリのセットアップ (uv)

`uv` を使用して、Pythonのバージョン管理、仮想環境の作成、依存関係のインストールを一元管理します。

### 4.1 プロジェクトの初期化とPythonバージョンの固定

```bash
# Python 3.14 をプロジェクトで使用するように固定
uv python pin 3.14
```
これにより `.python-version` ファイルが作成されます。

### 4.2 依存ライブラリの定義 (`pyproject.toml`)

`pyproject.toml` を編集し、必要なライブラリを追加します。
`uv` では `uv add` コマンドで依存関係を追加するのが推奨されますが、初期セットアップとして以下のコマンドを実行します。

```bash
# ランタイム依存関係の追加
uv add "aws-cdk-lib>=2.114.1" "constructs>=10.0.0" "aws-lambda-powertools[all]" "pydantic>=2.0.0"

# 開発用依存関係の追加 (テスト、Lintツールなど)
uv add --dev pytest ruff boto3 "boto3-stubs[dynamodb]" mypy
```

これにより `pyproject.toml` と `uv.lock` が自動的に更新されます。

### 4.3 Lambda Layer用 requirements.txt の準備

Lambda Layerの構築には `requirements.txt` が必要となります。
`pyproject.toml` で管理されている依存関係のうち、Lambda実行時に必要なもの（ランタイム依存）のみを抽出して記述します。

**`layers/common_layer/requirements.txt`**:
```text
aws-lambda-powertools[all]
pydantic>=2.0.0
```
※ `uv export` を用いて生成することも可能ですが、ここでは最小限の構成を手動で定義します。

### 4.4 動作確認

CDKが正しく動作するか確認します。
`uv run` を使うことで、仮想環境を明示的に activate することなくコマンドを実行できます。

```bash
uv run cdk list
```

エラーが出ずにスタック名（例: `ServerlessTripSagaPythonStack`）が表示されればOKです。

## 5. ディレクトリ構造の作成 (DDD Layering)

デフォルトのCDK構造に加え、アプリケーションコードを格納するディレクトリを作成します。
本プロジェクトでは、Lambda関数ごとに独立したディレクトリを持たせつつ、内部でレイヤーを分けます。

以下のコマンドを実行して、ディレクトリツリーを作成してください。

```bash
# アプリケーションコード格納用ルート
mkdir -p src/services

# 1. Flight Service (フライト予約)
mkdir -p src/services/flight/handlers
mkdir -p src/services/flight/applications
mkdir -p src/services/flight/domain
mkdir -p src/services/flight/infrastructure

# 2. Hotel Service (ホテル予約)
mkdir -p src/services/hotel/handlers
mkdir -p src/services/hotel/applications
mkdir -p src/services/hotel/domain
mkdir -p src/services/hotel/infrastructure

# 3. Payment Service (決済)
mkdir -p src/services/payment/handlers
mkdir -p src/services/payment/applications
mkdir -p src/services/payment/domain
mkdir -p src/services/payment/infrastructure

# 4. Shared Kernel (共通処理)
mkdir -p src/services/shared/domain
mkdir -p src/services/shared/utils

# 各ディレクトリをPythonパッケージとして認識させるための __init__.py 作成
find src/services -type d -exec touch {}/__init__.py \;
```

### 構成の説明
*   **`src/services/`**: 全マイクロサービスのコードを格納。
*   **`handlers/`**: Lambdaのエントリーポイント（リクエスト受け付け）。
*   **`applications/`**: ユースケースの調整役（ドメインとインフラの橋渡し）。
*   **`domain/`**: 純粋なビジネスロジック（外部依存なし）。
*   **`infrastructure/`**: DynamoDBなど外部リソースへのアクセス実装。
*   **`shared/`**: サービス間で共有する例外定義や基底クラス。

## 6. 次のステップ

これでプロジェクトの基盤は整いました。
次は、**[Hands-on 02: データ永続化層の実装 (DynamoDB)](./02-dynamodb-design.md)** に進み、データベースの構築を行います。

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/project-setup`
*   **コミットメッセージ**: `プロジェクト構成のセットアップ (uv移行)`
