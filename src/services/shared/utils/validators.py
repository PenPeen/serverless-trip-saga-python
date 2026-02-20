from decimal import Decimal


def to_decimal(v: object) -> Decimal:
    """任意の値を Decimal に変換する

    Pydantic の field_validator (mode="before") から呼び出すことを想定。
    すでに Decimal の場合はそのまま返し、それ以外は str 経由で変換する。
    """
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))
