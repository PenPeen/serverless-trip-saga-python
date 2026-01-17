# Hands-on 02: データ永続化層の実装 (DynamoDB)
## 目的
* Single Table Design の理解と実装

## DynamoDB テーブル設計
* **PK**: `TRIP#<uuid>`
* **SK**: `METADATA` | `FLIGHT#<id>` | `HOTEL#<id>`
* **GSI1**: 検索用 (Status, Date等)

## アーキテクチャに関する注記 (重要)
* **Microservices vs Monolith**: 本来のマイクロサービスでは「Database per Service (サービスごとにDBを分離する)」が原則です。
* **本ハンズオンの方針**: 今回は学習コストとインフラ管理の簡略化、およびトランザクション集約の学習のため、**Single Table Design** を採用します。本番環境でこのパターンを適用する場合、各サービスのアクセス権限(IAM)を厳密に制御するか、サービスごとにテーブルを物理的に分割することを検討してください。

## CDK実装
* `dynamodb.Table` を定義。Partition Key=`PK`, Sort Key=`SK`。
* `billing_mode=PAY_PER_REQUEST`