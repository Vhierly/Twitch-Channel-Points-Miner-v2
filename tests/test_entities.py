import pytest
from TwitchChannelPointsMiner.classes.entities.Bet import (
    Bet,
    BetSettings,
    Strategy,
    Condition,
    OutcomeKeys,
    FilterCondition,
    DelayMode,
)
from TwitchChannelPointsMiner.classes.entities.Stream import Stream


class TestBetSettings:
    def test_default_strategy(self):
        settings = BetSettings()
        settings.default()
        assert settings.strategy == Strategy.SMART

    def test_default_percentage(self):
        settings = BetSettings()
        settings.default()
        assert settings.percentage == 5

    def test_default_max_points(self):
        settings = BetSettings()
        settings.default()
        assert settings.max_points == 50000

    def test_default_stealth_mode(self):
        settings = BetSettings()
        settings.default()
        assert settings.stealth_mode is False

    def test_default_delay_mode(self):
        settings = BetSettings()
        settings.default()
        assert settings.delay_mode == DelayMode.FROM_END


class TestBetCalculate:
    def _create_bet(self, strategy=Strategy.SMART):
        outcomes = [
            {
                "id": "outcome-1",
                "title": "Yes",
                "color": "BLUE",
                OutcomeKeys.TOTAL_USERS: 700,
                OutcomeKeys.TOTAL_POINTS: 70000,
                "top_predictors": [{"points": 5000}],
            },
            {
                "id": "outcome-2",
                "title": "No",
                "color": "PINK",
                OutcomeKeys.TOTAL_USERS: 300,
                OutcomeKeys.TOTAL_POINTS: 30000,
                "top_predictors": [{"points": 3000}],
            },
        ]
        settings = BetSettings(strategy=strategy)
        settings.default()
        return Bet(outcomes, settings)

    def test_calculate_returns_dict(self):
        bet = self._create_bet()
        decision = bet.calculate(10000)
        assert isinstance(decision, dict)
        assert "choice" in decision
        assert "amount" in decision
        assert "id" in decision

    def test_calculate_smart_strategy(self):
        bet = self._create_bet(Strategy.SMART)
        decision = bet.calculate(10000)
        assert decision["choice"] is not None

    def test_calculate_most_voted(self):
        bet = self._create_bet(Strategy.MOST_VOTED)
        decision = bet.calculate(10000)
        assert decision["choice"] == 0  # 700 users > 300 users

    def test_calculate_high_odds(self):
        bet = self._create_bet(Strategy.HIGH_ODDS)
        decision = bet.calculate(10000)
        assert decision["choice"] is not None

    def test_calculate_amount_capped_by_max_points(self):
        bet = self._create_bet()
        bet.settings.max_points = 100
        decision = bet.calculate(100000)
        assert decision["amount"] <= 100

    def test_calculate_amount_capped_by_percentage(self):
        bet = self._create_bet()
        decision = bet.calculate(10000)
        assert decision["amount"] == 500  # 5% of 10000

    def test_calculate_zero_balance(self):
        bet = self._create_bet()
        decision = bet.calculate(0)
        assert decision["amount"] == 0


class TestBetSkip:
    def test_skip_no_filter(self):
        outcomes = [
            {"id": "1", "title": "A", "color": "BLUE"},
            {"id": "2", "title": "B", "color": "PINK"},
        ]
        settings = BetSettings()
        settings.default()
        bet = Bet(outcomes, settings)
        bet.decision = {"choice": 0}
        skip, _ = bet.skip()
        assert skip is False

    def test_skip_with_filter_skip(self):
        outcomes = [
            {"id": "1", "title": "A", "color": "BLUE", OutcomeKeys.TOTAL_USERS: 100},
            {"id": "2", "title": "B", "color": "PINK", OutcomeKeys.TOTAL_USERS: 50},
        ]
        settings = BetSettings()
        settings.default()
        settings.filter_condition = FilterCondition(
            by=OutcomeKeys.TOTAL_USERS, where=Condition.LTE, value=80
        )
        bet = Bet(outcomes, settings)
        bet.decision = {"choice": 0}
        skip, _ = bet.skip()
        assert skip is True


class TestStream:
    def test_stream_init(self):
        stream = Stream()
        assert stream.broadcast_id is None
        assert stream.title is None
        assert stream.minute_watched == 0
        assert stream.watch_streak_missing is True

    def test_stream_update(self):
        stream = Stream()
        stream.update(
            broadcast_id="123",
            title="Test Stream",
            game={"id": "1", "name": "TestGame", "displayName": "Test Game"},
            tags=[{"id": "tag1", "localizedName": "Tag 1"}],
            viewers_count=100,
        )
        assert stream.broadcast_id == "123"
        assert stream.title == "Test Stream"
        assert stream.viewers_count == 100

    def test_stream_update_minute_watched(self):
        stream = Stream()
        stream.update_minute_watched()
        assert stream.minute_watched == 0
        import time
        time.sleep(0.1)
        stream.update_minute_watched()
        assert stream.minute_watched > 0

    def test_stream_game_name(self):
        stream = Stream()
        assert stream.game_name() is None
        stream.game = {"id": "1", "name": "TestGame", "displayName": "Test Game"}
        assert stream.game_name() == "TestGame"

    def test_stream_game_id(self):
        stream = Stream()
        assert stream.game_id() is None
        stream.game = {"id": "1", "name": "TestGame", "displayName": "Test Game"}
        assert stream.game_id() == "1"
