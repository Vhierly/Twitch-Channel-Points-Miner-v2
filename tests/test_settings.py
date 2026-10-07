from TwitchChannelPointsMiner.classes.Settings import (
    Priority,
    FollowersOrder,
    Events,
    Settings,
)


class TestPriority:
    def test_priority_values(self):
        assert Priority.ORDER is not None
        assert Priority.STREAK is not None
        assert Priority.DROPS is not None
        assert Priority.SUBSCRIBED is not None
        assert Priority.POINTS_ASCENDING is not None
        assert Priority.POINTS_DESCENDING is not None
        assert Priority.LOW_PRIORITY is not None
        assert Priority.FAVORITE is not None


class TestFollowersOrder:
    def test_followers_order_values(self):
        assert FollowersOrder.ASC is not None
        assert FollowersOrder.DESC is not None

    def test_followers_order_str(self):
        assert str(FollowersOrder.ASC) == "ASC"
        assert str(FollowersOrder.DESC) == "DESC"


class TestEvents:
    def test_events_values(self):
        assert Events.STREAMER_ONLINE is not None
        assert Events.STREAMER_OFFLINE is not None
        assert Events.BET_WIN is not None
        assert Events.BET_LOSE is not None
        assert Events.DROP_CLAIM is not None
        assert Events.CHAT_MENTION is not None

    def test_events_get(self):
        assert Events.get("STREAMER_ONLINE") == Events.STREAMER_ONLINE
        assert Events.get("INVALID") is None


class TestSettings:
    def test_settings_slots(self):
        assert hasattr(Settings, '__slots__')
        assert "logger" in Settings.__slots__
        assert "streamer_settings" in Settings.__slots__
        assert "enable_analytics" in Settings.__slots__
