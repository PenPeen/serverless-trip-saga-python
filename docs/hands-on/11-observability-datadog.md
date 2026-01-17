# Hands-on 11: Observability (Datadog / X-Ray)
## 目的
* 分散システムの可視化と監視

## 監視ツールの選択
本ハンズオンでは高度な監視機能を持つ **Datadog** の導入手順を解説しますが、AWS標準機能のみで完結させたい場合は **CloudWatch ServiceLens (X-Ray)** を使用することも可能です。

## パターンA: Datadog 実装 (Advanced)
* **前提**: Datadog アカウントと API Key が必要です。
* `datadog-cdk-constructs-v2` を使用。
* Lambda Extension の導入、Trace/Log の連携。
* Step Functions の可視化。

## パターンB: AWS Native 実装 (Standard)
* **概要**: 追加アカウント不要で実装可能です。
* CDKで `tracing=Tracing.ACTIVE` を Lambda および Step Functions State Machine に設定。
* CloudWatch ServiceLens コンソールでサービスマップとトレースを確認。

## ブランチとコミットメッセージ

*   **ブランチ名**: `feature/observability`
*   **コミットメッセージ**: `可観測性の設定`
