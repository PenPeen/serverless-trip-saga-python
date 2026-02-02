import pytest

from services.hotel.domain.value_object.stay_period import StayPeriod


class TestStayPeriod:
    def test_valid_stay_period(self):
        stay_period = StayPeriod(check_in="2024-01-01", check_out="2024-01-03")
        assert stay_period.check_in == "2024-01-01"
        assert stay_period.check_out == "2024-01-03"

    def test_nights_calculation(self):
        stay_period = StayPeriod(check_in="2024-01-01", check_out="2024-01-03")
        assert stay_period.nights() == 2

    def test_single_night_stay(self):
        stay_period = StayPeriod(check_in="2024-01-01", check_out="2024-01-02")
        assert stay_period.nights() == 1

    def test_checkout_before_checkin_raises_error(self):
        with pytest.raises(
            ValueError, match="Check-out date must be after check-in date"
        ):
            StayPeriod(check_in="2024-01-03", check_out="2024-01-01")

    def test_same_date_raises_error(self):
        with pytest.raises(
            ValueError, match="Check-out date must be after check-in date"
        ):
            StayPeriod(check_in="2024-01-01", check_out="2024-01-01")

    def test_invalid_date_format_raises_error(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            StayPeriod(check_in="not-a-date", check_out="2024-01-03")
