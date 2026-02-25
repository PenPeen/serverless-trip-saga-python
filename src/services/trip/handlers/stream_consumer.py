import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.types import TypeDeserializer
from botocore.config import Config
from botocore.exceptions import ClientError

deserializer = TypeDeserializer()

dynamodb = boto3.resource("dynamodb", config=Config(tcp_keepalive=True))
search_table = dynamodb.Table(os.environ["SEARCH_TABLE_NAME"])


def deserialize_image(image: dict) -> dict:
    return {k: deserializer.deserialize(v) for k, v in image.items()}


def _to_dynamodb_value(value):
    """Decimal は Number 型のまま保持し、その他は文字列に変換する"""
    if isinstance(value, Decimal):
        return value
    return str(value)


def _build_update_expression(
    fields: dict,
) -> tuple[str, dict, dict]:
    set_parts = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    for i, (key, value) in enumerate(fields.items()):
        name_placeholder = f"#f{i}"
        value_placeholder = f":v{i}"
        set_parts.append(f"{name_placeholder} = {value_placeholder}")
        expression_attribute_names[name_placeholder] = key
        expression_attribute_values[value_placeholder] = _to_dynamodb_value(value)

    return (
        "SET " + ", ".join(set_parts),
        expression_attribute_names,
        expression_attribute_values,
    )


def _upsert(trip_id: str, fields: dict, event_time: str, updated_at_key: str) -> None:
    """べき等に upsert する。
    既存レコードのエンティティ固有タイムスタンプより古いイベントはスキップ
    """
    update_expr, names, values = _build_update_expression(fields)
    try:
        search_table.update_item(
            Key={"trip_id": trip_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression=(
                Attr(updated_at_key).not_exists()  # 初回 upsert
                | Attr(updated_at_key).lt(event_time)  # 新しいイベントのみ適用
            ),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            print(f"INFO: Skipped stale event for {trip_id} (key: {updated_at_key}).")
        else:
            raise


def _handle_flight(trip_id: str, item: dict, event_time: str) -> None:
    fields = {
        "flight_number": item.get("flight_number", ""),
        "departure_time": item.get("departure_time", ""),
        "arrival_time": item.get("arrival_time", ""),
        "flight_status": item.get("status", ""),
        "flight_updated_at": event_time,
    }
    _upsert(trip_id, fields, event_time, "flight_updated_at")


def _handle_hotel(trip_id: str, item: dict, event_time: str) -> None:
    fields = {
        "hotel_name": item.get("hotel_name", ""),
        "check_in_date": item.get("check_in_date", ""),
        "check_out_date": item.get("check_out_date", ""),
        "hotel_status": item.get("status", ""),
        "hotel_updated_at": event_time,
    }
    _upsert(trip_id, fields, event_time, "hotel_updated_at")


def _handle_payment(trip_id: str, item: dict, event_time: str) -> None:
    fields = {
        # Decimal のまま保持して Number 型で保存
        "total_amount": item.get("amount", Decimal("0")),
        "currency": item.get("currency", ""),
        "payment_status": item.get("status", ""),
        "payment_updated_at": event_time,
    }
    _upsert(trip_id, fields, event_time, "payment_updated_at")


def _handle_remove(trip_id: str, sk: str, event_time: str) -> None:
    """SK に基づいて該当エンティティのフィールドのみをクリアする"""
    if sk.startswith("FLIGHT#"):
        fields = {
            "flight_number": "",
            "departure_time": "",
            "arrival_time": "",
            "flight_status": "REMOVED",
            "flight_updated_at": event_time,
        }
        _upsert(trip_id, fields, event_time, "flight_updated_at")
    elif sk.startswith("HOTEL#"):
        fields = {
            "hotel_name": "",
            "check_in_date": "",
            "check_out_date": "",
            "hotel_status": "REMOVED",
            "hotel_updated_at": event_time,
        }
        _upsert(trip_id, fields, event_time, "hotel_updated_at")
    elif sk.startswith("PAYMENT#"):
        fields = {
            "total_amount": Decimal("0"),
            "currency": "",
            "payment_status": "REMOVED",
            "payment_updated_at": event_time,
        }
        _upsert(trip_id, fields, event_time, "payment_updated_at")
    else:
        return  # TRIP# など対象外エンティティの削除は無視


def lambda_handler(event: dict, context) -> None:
    for record in event.get("Records", []):
        event_name = record["eventName"]  # INSERT / MODIFY / REMOVE
        dynamodb_record = record["dynamodb"]

        # Streams の近似イベント時刻を ISO 文字列化（べき等比較に使用）
        approx_ts: float = dynamodb_record.get("ApproximateCreationDateTime", 0)
        event_time = datetime.fromtimestamp(approx_ts, tz=timezone.utc).isoformat()

        if event_name == "REMOVE":
            old_image_raw = dynamodb_record.get("OldImage")
            if not old_image_raw:
                print("WARN: REMOVE event received without OldImage. Skipping.")
                continue

            old_image = deserialize_image(old_image_raw)
            pk: str = old_image.get("PK", "")
            sk: str = old_image.get("SK", "")
            trip_id = pk.removeprefix("TRIP#")
            _handle_remove(trip_id, sk, event_time)
            continue

        new_image = deserialize_image(dynamodb_record["NewImage"])
        pk: str = new_image.get("PK", "")
        sk: str = new_image.get("SK", "")
        trip_id = pk.removeprefix("TRIP#")

        if sk.startswith("FLIGHT#"):
            _handle_flight(trip_id, new_image, event_time)
        elif sk.startswith("HOTEL#"):
            _handle_hotel(trip_id, new_image, event_time)
        elif sk.startswith("PAYMENT#"):
            _handle_payment(trip_id, new_image, event_time)
        # TRIP# など他のエンティティは無視
