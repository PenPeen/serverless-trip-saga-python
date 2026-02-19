# Hands-on 13: The Bible of Serverless Observability with Datadog (Enterprise Scale)

## はじめに: 500関数の「カオス」を支配する

Lambda関数が10個程度の環境と、500個を超える大規模環境では、可観測性の次元が異なります。
小規模ならGUIで一つずつ設定できますが、大規模環境では「自動化」「コード化」「統制」がなければ運用は破綻します。

本ガイドは、**「大規模Serverlessアーキテクチャ」** における Datadog の実践的かつ高度な運用マニュアルです。
WebエンジニアがSREとして現場に入った初日から「プロフェッショナル」として振る舞うために必要な、**IaC、コスト管理、セキュリティ、高度なデバッグ技術**を網羅しています。

---

## Chapter 1: Observability as Code (監視のコード化)

500個のLambdaに対して、ブラウザでモニターを作るのは自殺行為です。
**「ダッシュボードもモニターも、全てコード（Terraform/CDK）で管理する」** ことが、大規模環境の絶対条件です。

### 1.1 Datadog Provider for Terraform / CDK
インフラと同じプルリクエストで、監視設定もレビュー・デプロイされるべきです。

**【実践コード例 (Terraform)】**
「全てのLambdaにエラーレートのアラートを自動設定する」モジュールのイメージ。

```hcl
resource "datadog_monitor" "lambda_error_rate" {
  name    = "[${var.env}] Lambda Error Rate High: {{service.name}}"
  type    = "query alert"
  query   = "avg(last_5m):default_zero(sum:aws.lambda.errors{env:${var.env}, service:${var.service_name}}) / default_zero(sum:aws.lambda.invocations{env:${var.env}, service:${var.service_name}}) > 0.05"
  message = <<EOT
  {{service.name}} のエラー率が5%を超えました。
  Logs: [Dashboard Link]
  @slack-${var.team_channel}
  EOT
  
  tags = ["env:${var.env}", "service:${var.service_name}", "terraform:true"]
}
```

### 1.2 "Monitor Json" Pattern
Terraformのリソース定義だけでは複雑なダッシュボードを表現しきれない場合、DatadogのUIで作成したダッシュボードのJSONをエクスポートし、それをコードリポジトリで管理・インポートする手法も有効です。

---

## Chapter 2: Advanced Tracing Strategy (高度なトレース戦略)

リクエスト数が億単位になると、全トレース取得は経済的にも技術的にも不可能です。
「何を捨て、何を残すか」の意思決定がSREの腕の見せ所です。

### 2.1 Trace Context Propagation (コンテキスト伝播の完全化)
SQS, EventBridge, Kinesis などを経由する非同期アーキテクチャでは、デフォルト設定だけではトレースが分断されます。

*   **鉄則**: `aws-lambda-powertools` (Python) または `datadog-lambda` レイヤーを使用し、分散トレーシングを有効化。
*   **環境変数**: `DD_TRACE_ENABLED=true`, `DD_LOGS_INJECTION=true`

### 2.2 Intelligent Sampling (サンプリング戦略)
*   **Head-based Sampling**: API Gatewayなどの入り口で `DD_TRACE_SAMPLE_RATE` を設定（Prod: 5-10%）。
*   **Retention Filters (Tag-based)**:
    *   「エラーが発生したトレース」は **100% 保持**。
    *   「特定の重要顧客（`customer_id:premium`）」のトレースは **100% 保持**。
    *   それ以外はランダムサンプリング。
    *   これらを **Datadog UI上の "Retention Filters"** で設定します（コード変更不要）。

---

## Chapter 3: Log Management & Cost Control (ログ管理とコスト最適化)

「ログは全て保存する」は破産への近道です。ログの価値に応じて保存先を振り分けます。

### 3.1 Exclusion Filters & Indexing Strategy
Lambdaの標準出力は膨大です。以下の戦略でコストを90%削減します。

1.  **Exclude from Index**: `START RequestId`, `END RequestId`, `REPORT RequestId` などのAWS基盤ログは、Index（検索対象）から除外し、Live Tailのみで見えるように設定。
2.  **Log Archives**: コンプライアンス上保存が必要だが、普段は見ないログ（正常系のアクセスログなど）は、**S3へのアーカイブ（Log Archives）** に送る。Datadogには保存しない。
3.  **Rehydration**: アーカイブしたログが必要になった時だけ、特定の時間帯・クエリでDatadogに書き戻す機能を使用。

### 3.2 Sensitive Data Masking (PII保護)
ログにクレジットカード番号や個人情報が含まれると大事故です。
**Scanner** プロセッサを設定し、正規表現でPII（個人特定情報）を検出し、Datadog保存前にハッシュ化または置換（Redact）します。

---

## Chapter 4: Database & Dependency Deep Dive (DBと依存関係)

Lambdaが遅い原因の7割はDBか外部APIです。

### 4.1 DynamoDB Hot Partition & Throttling
AWS統合メトリクスだけでなく、アプリケーション側からの視点を強化します。

*   **Metric**: `aws.dynamodb.provisioned_throughput_exceeded` だけでは不十分。
*   **Span Tags**: アプリケーションのSpanに `db.statement` (実行したクエリ), `table_name` を付与し、どのクエリが遅いかを特定できるようにする。

### 4.2 External API Monitoring
決済GWや他社APIへの依存はリスクです。
*   外部APIへのHTTPリクエストを `service:payment-gateway` のように仮想サービスとして定義し、その **Availability (可用性)** と **Latency** を個別に監視します。

---

## Chapter 5: Continuous Profiler (コードレベルの深掘り)

「なぜか遅い」「メモリリークしている」といった、ログやトレースでは分からない問題には **Continuous Profiler** が必須です。

### 5.1 本番環境での常時プロファイリング
オーバーヘッドは極めて低いため、本番でも有効化します。

*   **Wall Time Profiling**: I/O待ち（DB応答待ちなど）の時間内訳。
*   **CPU Profiling**: 高負荷な計算処理（画像の加工、暗号化など）の特定。
*   **Memory Profiling**: メモリリークや非効率なオブジェクト生成の特定。

これにより、「この関数の30行目のループ処理がCPUの40%を消費している」といったレベルまで特定できます。

---

## Chapter 6: Intelligent Alerting & SLO (アラート戦略)

### 6.1 SLO (Service Level Objectives) & Burn Rate
「エラーが出た」でアラートを飛ばすのは二流です。「ユーザーとの約束（SLO）が破られそうだ」で飛ばします。

*   **SLO**: 99.9% の成功率（月間ダウンタイム許容: 約43分）。
*   **Burn Rate Alert**: 「このままのペースでエラーが続くと、あと2時間でエラー予算が尽きる」という速度（Burn Rate）を検知してアラート。これにより、散発的なエラーでの深夜の叩き起こしを防ぎます。

### 6.2 Composite Monitors
誤検知を防ぐ最強の武器です。
*   Monitor A: エラー率 > 5%
*   Monitor B: リクエスト数 > 50/min
*   **Composite**: `Monitor A && Monitor B`
（「エラー率が高い」かつ「トラフィックがある」時だけ通知）

---

## Chapter 7: Security (ASM & Cloud SIEM)

SREの責任範囲はセキュリティにも及びます。

### 7.1 Application Security Management (ASM)
Datadog ASMを有効化することで、ライブラリの脆弱性検知だけでなく、実行時の攻撃（SQLインジェクション、XSS、SSRFなど）を検知・ブロックできます。
WAFでは防ぎきれない、アプリケーション内部の挙動ベースの防御です。

### 7.2 Cloud SIEM
CloudTrailログやVPC Flow LogsをDatadogに取り込み、不審なAWS APIコール（権限昇格の試み、普段使わないリージョンでのインスタンス起動など）を検知します。

---

## Chapter 8: CI/CD Pipeline Visibility

デプロイ頻度が高い環境では、CI/CD自体がボトルネックになります。

### 8.1 Pipeline Monitoring
GitHub Actions や CodePipeline と連携し、以下のメトリクスを可視化します。
*   **Build Duration**: ビルドにかかる時間の推移。
*   **Failure Rate**: テストの失敗率、デプロイの失敗率。
*   **Flaky Tests**: 「時々失敗するテスト」の特定と駆除。

---

## Chapter 9: Hands-on User Stories (現場で起きる「あの」障害への処方箋)

座学だけでは現場は戦えません。
ここでは、大規模環境で頻発する**5つの具体的シナリオ**に対して、Datadogを使った「最短の犯人特定フロー」をハンズオン形式で解説します。

### Scenario 1: 「APIが遅い」と言われたが、どこが遅いか分からない
**状況**: ユーザーから「検索が遅い」とクレームが来た。平均レイテンシは正常だが、p95が悪化している。

**【捜査フロー】**
1.  **APM > Traces** を開く。
2.  Filter: `service:search-service`, `env:prod`。
3.  Sort by: **Duration (desc)**。
4.  最も遅いトレース（Flame Graph）をクリックし、**Gap Analysis** を行う。
    *   **Case A**: Lambda開始前に長い空白がある -> **Cold Start**。Provisioned Concurrencyを検討。
    *   **Case B**: `aws.dynamodb` のSpanが異常に長い -> **DynamoDB Latency**。インデックス不足かデータ量過多。
    *   **Case C**: Spanの隙間がなく、ただ処理時間が長い -> **CPU Bottleneck**。Profilerを見るか、メモリ割り当てを増やす。

### Scenario 2: 夜間だけ謎のエラーが発生する
**状況**: 毎晩3:00頃にエラーレートがスパイクするが、朝には直っている。

**【捜査フロー】**
1.  **Dashboard** で時間帯を絞り込む。
2.  **Log Overlay** 機能を使い、エラースパイクと同時刻のログを表示。
3.  **Error Tracking** 画面で、Issueのグルーピングを確認。
    *   **犯人**: `ConnectionTimeout` が外部バッチ処理（他社システム）と連携するタイミングで多発。
4.  **Action**: 相手側システムのメンテナンス時間と被っていないか確認し、リトライ戦略（Exponential Backoff）を調整。

### Scenario 3: DynamoDBがスロットリングしているが、全体キャパシティには余裕がある
**状況**: `ProvisionedThroughputExceededException` が出ているが、テーブル全体の消費RCUは上限の10%以下。

**【捜査フロー】**
1.  **APM** で該当エラーのトレースを開く。
2.  Span Tags の `db.statement` (実行されたクエリ) を確認。
    *   例: `SELECT * FROM Orders WHERE status = 'PENDING'`
3.  **犯人**: 特定のPartition Key（例: 大口顧客のID）にアクセスが集中する **Hot Partition** 問題。
4.  **Action**: テーブル設計を見直し、Write Shardingなどを検討。またはOn-Demandモードへの切り替え。

### Scenario 4: N+1問題によるパフォーマンス劣化
**状況**: 一つのリクエストでDynamoDBへのコール数が異常に多い。

**【捜査フロー】**
1.  **APM > Traces** でリストを表示。
2.  Measure: **Span Count** を追加してソート。
3.  一つのトレース内で `aws.dynamodb` のSpanが100回以上連続している箇所を発見。
4.  **犯人**: ループ内で `getItem` をしている典型的な **N+1問題**。
5.  **Action**: `batchGetItem` または `Query` を使い、1回のリクエストでまとめて取得するようにコードを修正。

### Scenario 5: 「処理は成功しているのに、結果が反映されていない」（Silent Failure）
**状況**: エラーログは出ていないが、ユーザーから「予約が完了していない」と言われる。

**【捜査フロー】**
1.  **Logs** で `user_id` で検索し、一連のフローを追う。
2.  Status: `Info` のログも含めて確認。
3.  **犯人**: `try-catch` ブロックで例外を握りつぶし、`logger.error` を出さずに `return None` しているコードを発見。
4.  **Action**:
    *   例外を握りつぶさない。
    *   Datadogの **Custom Metric** (`app.booking.failure_count`) をインクリメントする処理を追加し、ビジネスロジック上の失敗を可視化する。

---

## まとめ: プロフェッショナルSREのチェックリスト

500関数の大規模環境において、以下の準備ができているか自問してください。

1.  **IaC**: 監視設定はTerraform/CDKで管理されているか？
2.  **Cost Efficiency**: ログの除外設定とアーカイブ活用で、無駄なコストを削減しているか？
3.  **Trace**: 非同期処理を含め、Trace ID が途切れず繋がっているか？
4.  **Database**: DynamoDBのホットキーやクエリ遅延を特定できるか？
5.  **Profiling**: コードレベルのボトルネック（CPU/メモリ）を特定できるか？
6.  **Security**: アプリケーションへの攻撃や脆弱性をリアルタイムで検知できるか？
7.  **SLO**: ユーザー影響に基づいたアラート（Burn Rate）が設定されているか？

これらをクリアした時、あなたはDatadogを「監視ツール」としてではなく、「ビジネスの信頼性を担保するプラットフォーム」として使いこなしていると言えるでしょう。
