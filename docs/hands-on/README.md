# ハンズオン実行計画: Serverless Trip Saga

`docs/01_architecture_and_design.md` のアーキテクチャに基づき、理解を深めながら順次実装を進めるためのハンズオン計画です。
各ステップは `docs/hands-on/` ディレクトリ配下に、連番付きのMarkdownファイル (`01-xxx.md`) として作成・実施していきます。

## 全体ゴール
AWS Serverlessサービス (Lambda, Step Functions, DynamoDB) を活用し、Sagaパターンを用いた堅牢な旅行予約システムを構築する。

## ハンズオン構成案

### Phase 1: プロジェクト基盤の構築
**目的**: 開発環境のセットアップと、IaC (AWS CDK) の基本構造を理解する。

*   **`docs/hands-on/01-project-setup.md`**
    *   **内容**:
        *   Prerequisites の確認 (Python, Node, AWS CLI, CDK)。
        *   CDKプロジェクトの初期化 (`cdk init`)。
        *   仮想環境のセットアップと依存ライブラリ (`requirements.txt`) のインストール。
        *   Project Structure (DDDレイヤー構造) のディレクトリ作成。
    *   **成果物**: `cdk deploy` 可能な初期状態のプロジェクト。

### Phase 2: データ永続化層の実装 (DynamoDB)
**目的**: Single Table Design の設計意図と、CDKによるリソース定義を学ぶ。

*   **`docs/hands-on/02-dynamodb-design.md`**
    *   **内容**:
        *   DynamoDB テーブル設計の解説 (PK/SK, GSI, Outbox Pattern)。
        *   CDK Stack への DynamoDB 定義の追加。
        *   ローカルでの設計検証 (NoSQL Workbench 等の活用など、概念理解)。
    *   **成果物**: アプリケーション用 DynamoDB テーブルのデプロイ。

### Phase 3: マイクロサービス実装 (Lambda & Layers)
**目的**: DDDに基づいたLambdaの実装パターンと、共通処理の効率化、および品質担保（テスト）を学ぶ。

*   **`docs/hands-on/03-shared-kernel-and-layers.md`**
    *   **内容 (Review反映)**:
        *   共通ライブラリ (Powertools, Pydantic) の Lambda Layer 化。
        *   **[追加] Shared Kernel の実装**: 全サービスで共通利用する例外クラス、DDD基底クラス、ログ設定などを実装し、各サービスの重複コードを排除する。
    *   **成果物**: 共通 Layer のデプロイ、共通モジュールの作成。

*   **`docs/hands-on/04-service-implementation-flight.md`**
    *   **内容 (Review反映)**:
        *   **Flight Service** の実装 (DDD構成: `handlers`, `applications`, `domain`, `infrastructure`)。
        *   **[追加] Unit Testing**: ビジネスロジック (Domain/Application) の単体テストを作成し、デプロイ前に品質を担保するサイクルを回す。
        *   DynamoDB への書き込み実装。
    *   **成果物**: テスト済みの Flight Lambda 関数。

*   **`docs/hands-on/05-service-implementation-hotel-payment.md`**
    *   **内容**:
        *   **Hotel Service** (予約 & 補償/キャンセル) の実装。
        *   **Payment Service** の実装。
        *   共通化された基盤を利用することで、開発効率が上がっていることを体感する。
    *   **成果物**: 3つのマイクロサービス (Flight, Hotel, Payment) の Lambda 関数（テスト済み）。

### Phase 4: Saga オーケストレーション (Step Functions)
**目的**: 分散トランザクションの制御フローと、補償トランザクションの実装を学ぶ。

*   **`docs/hands-on/06-step-functions-orchestration.md`**
    *   **内容**:
        *   ASL (Amazon States Language) と CDK Chain Definition。
        *   **正常系フロー** (Flight -> Hotel -> Payment) の定義。
        *   Step Functions から Lambda へのパラメータ受け渡し。
    *   **成果物**: 正常に予約完了する Saga フロー。

*   **`docs/hands-on/07-saga-compensation.md`**
    *   **内容**:
        *   **異常系フロー** と `Catch` ブロックの定義。
        *   補償トランザクション (各サービスのキャンセル処理) の呼び出し。
        *   フォールバック戦略の実装。
    *   **成果物**: 失敗時にロールバックを行う完全な Saga フロー。

### Phase 5: インターフェース公開 (API Gateway)
**目的**: 外部からのアクセスポイントを作成し、システム全体を結合する。

*   **`docs/hands-on/08-api-gateway-integration.md`**
    *   **内容**:
        *   API Gateway の構築 (Rest API or HTTP API)。
        *   Step Functions への直接統合 (AWS Service Integration)。
        *   リクエストバリデーション。
    *   **成果物**: API エンドポイント経由で予約フローを実行可能にする。

### Phase 6: プロダクション・レディ (CI/CD & Observability)
**目的**: 継続的デリバリーと運用のための高度な設定を学ぶ。

*   **`docs/hands-on/09-cicd-codepipeline.md`**
    *   **内容**:
        *   CodePipeline, CodeBuild による自動デプロイパイプラインの構築。
        *   **[修正] テスト自動化**: Phase 3で作成した単体テストをビルドプロセスに組み込む。
    *   **成果物**: GitHub への Push でテスト実行＆自動デプロイされるパイプライン。

*   **`docs/hands-on/10-canary-deployment.md`**
    *   **内容**:
        *   CodeDeploy を用いた Lambda の Canary リリース (10% Traffic Shifting) 設定。
        *   CloudWatch Alarms による自動ロールバック設定。
    *   **成果物**: 安全なデプロイ戦略の実装。

*   **`docs/hands-on/11-observability-datadog.md`**
    *   **内容**:
        *   Datadog との連携設定 (Extension / Forwarder)。
        *   分散トレーシングの確認。
        *   カスタムメトリクスの可視化。
    *   **成果物**: システムの稼働状況を可視化するダッシュボード。

### Phase 7: 検索基盤の追加 (DynamoDB Streams + Search Table)
**目的**: DynamoDB Streams を使ったイベント駆動の検索用テーブル同期パターンを学ぶ。

*   **`docs/hands-on/15_dynamodb_streams_search_table.md`**
    *   **内容**:
        *   DynamoDB Streams の概念とイベント構造の解説。
        *   検索用テーブル (`TripSearchTable`) の設計と CDK への追加。
        *   Stream Consumer Lambda で CQRS 的に非正規化ドキュメントを同期する実装。
        *   複合条件検索（ステータス・出発日範囲）のクエリ Lambda の実装。
    *   **成果物**: Streams 駆動で自動同期される検索用テーブルと、絞り込み検索 API。