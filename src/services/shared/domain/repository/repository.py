from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
ID = TypeVar("ID")


class Repository(ABC, Generic[T, ID]):
    """Repository 基底クラス

    - 集約の永続化を抽象化する
    """

    @abstractmethod
    def save(self, aggregate: T) -> None:
        """集約を永続化する"""
        raise NotImplementedError

    @abstractmethod
    def find_by_id(self, id: ID) -> T | None:
        """IDで集約を検索する"""
        raise NotImplementedError
