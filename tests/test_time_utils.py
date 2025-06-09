"""Tests for time parsing utilities."""

import pytest

from roon_display.time_utils import parse_time_to_minutes, parse_time_to_seconds


class TestParseTimeToSeconds:
    """Test cases for parse_time_to_seconds function."""

    def test_plain_integers(self):
        """Test parsing plain integers."""
        assert parse_time_to_seconds(600) == 600
        assert parse_time_to_seconds("600") == 600
        assert parse_time_to_seconds("  300  ") == 300

    def test_seconds(self):
        """Test parsing second expressions."""
        assert parse_time_to_seconds("30s") == 30
        assert parse_time_to_seconds("30 s") == 30
        assert parse_time_to_seconds("45 sec") == 45
        assert parse_time_to_seconds("60 secs") == 60
        assert parse_time_to_seconds("15 second") == 15
        assert parse_time_to_seconds("90 seconds") == 90

    def test_minutes(self):
        """Test parsing minute expressions."""
        assert parse_time_to_seconds("5m") == 300
        assert parse_time_to_seconds("5 m") == 300
        assert parse_time_to_seconds("10 min") == 600
        assert parse_time_to_seconds("15 mins") == 900
        assert parse_time_to_seconds("30 minute") == 1800
        assert parse_time_to_seconds("45 minutes") == 2700

    def test_hours(self):
        """Test parsing hour expressions."""
        assert parse_time_to_seconds("1h") == 3600
        assert parse_time_to_seconds("1 h") == 3600
        assert parse_time_to_seconds("2 hr") == 7200
        assert parse_time_to_seconds("3 hrs") == 10800
        assert parse_time_to_seconds("1 hour") == 3600
        assert parse_time_to_seconds("24 hours") == 86400

    def test_days(self):
        """Test parsing day expressions."""
        assert parse_time_to_seconds("1d") == 86400
        assert parse_time_to_seconds("1 d") == 86400
        assert parse_time_to_seconds("1 day") == 86400
        assert parse_time_to_seconds("2 days") == 172800

    def test_decimal_numbers(self):
        """Test parsing decimal numbers."""
        assert parse_time_to_seconds("1.5 minutes") == 90
        assert parse_time_to_seconds("2.5h") == 9000
        assert parse_time_to_seconds("0.5 hours") == 1800

    def test_case_insensitive(self):
        """Test case insensitive parsing."""
        assert parse_time_to_seconds("5 MINUTES") == 300
        assert parse_time_to_seconds("10 Min") == 600
        assert parse_time_to_seconds("2 Hours") == 7200

    def test_invalid_formats(self):
        """Test invalid time formats."""
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds("invalid")

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds("5 mins 30 secs")

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds("")

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds("   ")

    def test_unknown_units(self):
        """Test unknown time units."""
        with pytest.raises(ValueError, match="Unknown time unit"):
            parse_time_to_seconds("5 weeks")

        with pytest.raises(ValueError, match="Unknown time unit"):
            parse_time_to_seconds("10 xyz")

    def test_invalid_numbers(self):
        """Test invalid numbers."""
        with pytest.raises(ValueError, match="Invalid number"):
            parse_time_to_seconds("abc minutes")

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds("minutes")

    def test_non_string_non_int_input(self):
        """Test non-string, non-integer input."""
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds(None)

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_to_seconds([])


class TestParseTimeToMinutes:
    """Test cases for parse_time_to_minutes function."""

    def test_basic_conversion(self):
        """Test basic conversion to minutes."""
        assert parse_time_to_minutes("60 seconds") == 1
        assert parse_time_to_minutes("120 seconds") == 2
        assert parse_time_to_minutes("5 minutes") == 5
        assert parse_time_to_minutes("1 hour") == 60
        assert parse_time_to_minutes("1.5 hours") == 90

    def test_plain_integers(self):
        """Test parsing plain integers (assumed to be seconds)."""
        assert parse_time_to_minutes(60) == 1
        assert parse_time_to_minutes(3600) == 60
        assert parse_time_to_minutes("120") == 2

    def test_rounding(self):
        """Test rounding to integer minutes."""
        # 30 seconds = 0.5 minutes, should round down to 0
        assert parse_time_to_minutes("30 seconds") == 0
        # 90 seconds = 1.5 minutes, should round down to 1
        assert parse_time_to_minutes("90 seconds") == 1
        # 150 seconds = 2.5 minutes, should round down to 2
        assert parse_time_to_minutes("150 seconds") == 2


class TestTimeUtilsIntegration:
    """Integration tests for time utilities."""

    def test_common_anniversary_formats(self):
        """Test formats commonly used for anniversary wait times."""
        assert parse_time_to_minutes("30") == 30  # Backward compatibility
        assert parse_time_to_minutes("30 minutes") == 30
        assert parse_time_to_minutes("1 hour") == 60
        assert parse_time_to_minutes("2h") == 120

    def test_common_loop_time_formats(self):
        """Test formats commonly used for loop times."""
        assert parse_time_to_seconds("600") == 600  # Backward compatibility
        assert parse_time_to_seconds("10 minutes") == 600
        assert parse_time_to_seconds("5 mins") == 300
        assert parse_time_to_seconds("30 seconds") == 30

    def test_common_health_interval_formats(self):
        """Test formats commonly used for health check intervals."""
        assert parse_time_to_seconds("1800") == 1800  # Backward compatibility
        assert parse_time_to_seconds("30 minutes") == 1800
        assert parse_time_to_seconds("1 hour") == 3600
        assert parse_time_to_seconds("2h") == 7200
