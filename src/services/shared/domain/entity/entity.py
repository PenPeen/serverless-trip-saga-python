from abc import ABC
from typing import Generic, TypeVar

ID = TypeVar("ID")


class Entity(ABC, Generic[ID]):
    """Entity 基底クラス"""

    def __init__(self, id: ID) -> None:
        self._id = id

    @property
    def id(self) -> ID:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)
