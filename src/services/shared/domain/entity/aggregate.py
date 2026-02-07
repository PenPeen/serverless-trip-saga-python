from typing import TypeVar

from .entity import Entity

ID = TypeVar("ID")


class AggregateRoot(Entity[ID]):
    """AggregateRoot 基底クラス

    - 配下のエンティティへのアクセスは必ず集約ルートを経由
    - トランザクション境界 = 集約境界
    """

    def __init__(self, id: ID) -> None:
        super().__init__(id)
        self._domain_events: list = []

    def add_domain_event(self, event: object) -> None:
        """ドメインイベントを追加する"""
        self._domain_events.append(event)

    def flush_domain_events(self) -> list:
        """ドメインイベントをクリアする"""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events
