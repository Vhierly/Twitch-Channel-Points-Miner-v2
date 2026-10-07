import pytest
from TwitchChannelPointsMiner.utils import (
    _millify,
    percentage,
    float_round,
    create_nonce,
    remove_emoji,
    internet_connection_available,
)


class TestMillify:
    def test_millify_thousands(self):
        assert _millify(1000) == "1.00K"

    def test_millify_millions(self):
        assert _millify(1000000) == "1.00M"

    def test_millify_billions(self):
        assert _millify(1000000000) == "1.00B"

    def test_millify_zero(self):
        assert _millify(0) == "0.00"

    def test_millify_small_number(self):
        assert _millify(500) == "500.00"


class TestPercentage:
    def test_percentage_normal(self):
        assert percentage(50, 100) == 50

    def test_percentage_zero_numerator(self):
        assert percentage(0, 100) == 0

    def test_percentage_zero_denominator(self):
        assert percentage(50, 0) == 0

    def test_percentage_both_zero(self):
        assert percentage(0, 0) == 0

    def test_percentage_over_100(self):
        assert percentage(150, 100) == 150


class TestFloatRound:
    def test_float_round_normal(self):
        assert float_round(3.14159, 2) == 3.14

    def test_float_round_zero(self):
        assert float_round(0, 2) == 0

    def test_float_round_negative(self):
        assert float_round(-3.14159, 2) == -3.14


class TestCreateNonce:
    def test_create_nonce_length(self):
        nonce = create_nonce(30)
        assert len(nonce) == 30

    def test_create_nonce_default_length(self):
        nonce = create_nonce()
        assert len(nonce) == 30

    def test_create_nonce_alphanumeric(self):
        nonce = create_nonce(100)
        assert nonce.isalnum()


class TestRemoveEmoji:
    def test_remove_emoji_basic(self):
        assert remove_emoji("Hello 😀 World") == "Hello  World"

    def test_remove_emoji_no_emoji(self):
        assert remove_emoji("Hello World") == "Hello World"

    def test_remove_emoji_only_emoji(self):
        assert remove_emoji("😀😃😄") == ""


class TestInternetConnection:
    def test_internet_connection_available(self):
        # This may fail in offline environments, so we just check it returns a bool
        result = internet_connection_available()
        assert isinstance(result, bool)
