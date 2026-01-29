import pytest

from services.flight.domain.value_object import FlightNumber


class TestFlightNumber:
    """FlightNumber のテスト"""

    def test_valid_flight_number(self):
        """フライト番号を生成できる"""
        flight_number = FlightNumber("NH001")
        assert flight_number.value == "NH001"
        assert flight_number.airline_code == "NH"
        assert flight_number.flight_num == "001"

    def test_lowercase_is_normalized(self):
        """小文字は大文字に正規化される"""
        flight_number = FlightNumber("nh001")
        assert flight_number.value == "NH001"

    def test_invalid_format_raises_error(self):
        """不正な形式が渡された場合、例外が発生する"""
        with pytest.raises(
            ValueError,
            match="Invalid flight number format: XXXXX",
        ):
            FlightNumber("XXXXX")
