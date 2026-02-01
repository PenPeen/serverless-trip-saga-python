import pytest

from services.hotel.domain.value_object.hotel_name import HotelName


class TestHotelName:
    def test_valid_hotel_name(self):
        hotel_name = HotelName(value="Grand Hotel")
        assert hotel_name.value == "Grand Hotel"

    def test_str_returns_value(self):
        hotel_name = HotelName(value="Grand Hotel")
        assert str(hotel_name) == "Grand Hotel"

    def test_empty_name_raises_error(self):
        with pytest.raises(ValueError, match="Hotel name cannot be empty"):
            HotelName(value="")

    def test_whitespace_only_name_raises_error(self):
        with pytest.raises(ValueError, match="Hotel name cannot be empty"):
            HotelName(value="   ")

    def test_too_long_name_raises_error(self):
        with pytest.raises(ValueError, match="Hotel name is too long"):
            HotelName(value="A" * 101)

    def test_max_length_name_is_valid(self):
        hotel_name = HotelName(value="A" * 100)
        assert len(hotel_name.value) == 100
