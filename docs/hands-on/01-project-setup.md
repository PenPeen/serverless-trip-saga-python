# Hands-on 01: プロジェクト基盤の構築

本ハンズオンの第一歩として、AWS CDKを用いたPythonプロジェクトの初期化を行い、ドメイン駆動設計 (DDD) に適したディレクトリ構造をセットアップします。

## 1. 目的
*   AWS CDK (Python) の開発環境を整える。
*   プロジェクトの依存ライブラリをインストールする。
*   将来的な拡張（マイクロサービス化）に備えた、明確なレイヤー構造を作成する。

## 2. 前提条件 (Prerequisites)
以下のツールがインストールされていることを確認してください。

*   **Python 3.9 以上**: `python --version`
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

## 4. 仮想環境と依存ライブラリのセットアップ

Pythonの仮想環境を有効化し、必要なライブラリをインストールします。

### 4.1 仮想環境の有効化

```bash
# Mac / Linux
source .venv/bin/activate

# Windows (参考)
# .venv\Scripts\activate
```

### 4.2 依存ライブラリの定義

プロジェクトルートにある `requirements.txt` を編集し、以下のライブラリを追加します。
これらはAWS Lambdaの実装や型定義に必要となります。

**`requirements.txt`**:
```text
aws-cdk-lib==2.114.1
constructs>=10.0.0
aws-lambda-powertools[all]
pydantic>=2.0.0
pytest
```

*   `aws-lambda-powertools[all]`: ログ出力、トレース、メトリクスなどのユーティリティ。
*   `pydantic`: データバリデーション用。
*   `pytest`: テスト用フレームワーク。

### 4.3 インストール

```bash
pip install -r requirements.txt
```

### 4.4 動作確認

CDKが正しく動作するか確認します。

```bash
cdk list
```

エラーが出ずにスタック名（例: `ServerlessTripSagaPythonStack`）が表示されればOKです。

## 5. ディレクトリ構造の作成 (DDD Layering)

デフォルトのCDK構造に加え、アプリケーションコードを格納するディレクトリを作成します。
本プロジェクトでは、Lambda関数ごとに独立したディレクトリを持たせつつ、内部でレイヤーを分けます。

以下のコマンドを実行して、ディレクトリツリーを作成してください。

```bash
# アプリケーションコード格納用ルート
mkdir -p services

# 1. Flight Service (フライト予約)
mkdir -p services/flight/handlers
mkdir -p services/flight/applications
mkdir -p services/flight/domain
mkdir -p services/flight/adapters

# 2. Hotel Service (ホテル予約)
mkdir -p services/hotel/handlers
mkdir -p services/hotel/applications
mkdir -p services/hotel/domain
mkdir -p services/hotel/adapters

# 3. Payment Service (決済)
mkdir -p services/payment/handlers
mkdir -p services/payment/applications
mkdir -p services/payment/domain
mkdir -p services/payment/adapters

# 4. Shared Kernel (共通処理)
mkdir -p services/shared/domain
mkdir -p services/shared/utils

# 各ディレクトリをPythonパッケージとして認識させるための __init__.py 作成
find services -type d -exec touch {}/__init__.py \;
```

### 構成の説明
*   **`services/`**: 全マイクロサービスのコードを格納。
*   **`handlers/`**: Lambdaのエントリーポイント（リクエスト受け付け）。
*   **`applications/`**: ユースケースの調整役（ドメインとインフラの橋渡し）。
*   **`domain/`**: 純粋なビジネスロジック（外部依存なし）。
*   **`adapters/`**: DynamoDBなど外部リソースへのアクセス実装。
*   **`shared/`**: サービス間で共有する例外定義や基底クラス。

## 6. 次のステップ

これでプロジェクトの基盤は整いました。
次は、**[Hands-on 02: データ永続化層の実装 (DynamoDB)](./02-dynamodb-design.md)** に進み、データベースの構築を行います。

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/project-setup`
*   **コミットメッセージ**: `プロジェクト構成のセットアップ`
