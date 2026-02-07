from unittest.mock import MagicMock

import pytest

from services.shared.domain.value_object.trip_id import TripId


@pytest.fixture
def trip_id():
    """全テスト共通の TripId フィクスチャ"""
    return TripId(value="trip-123")


@pytest.fixture
def mock_repository():
    """リポジトリのモックフィクスチャ"""
    return MagicMock()
