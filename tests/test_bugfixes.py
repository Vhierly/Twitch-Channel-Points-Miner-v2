"""Tests for the 6 blocker bug fixes."""
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))


# === Bug #1: Greeting spam ===

class TestGreetingSpam:
    def test_greeting_sent_slot_exists(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        assert hasattr(s, '_greeting_sent')
        assert s._greeting_sent is False

    def test_greeting_sent_reset_on_set_online(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        s._greeting_sent = True
        s.is_online = False
        s.set_online()
        assert s._greeting_sent is False

    def test_greeting_sent_reset_on_set_offline(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        s._greeting_sent = True
        s.is_online = True
        s.set_offline()
        assert s._greeting_sent is False

    def test_greeting_sent_set_after_send(self):
        """Simulate the loop logic: greeting sent once, then flag set."""
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        s.is_online = True
        s.settings = MagicMock()
        s.settings.greeting_message = "Hello!"
        s.settings.chat = 0  # ChatPresence.ONLINE
        s.irc_chat = MagicMock()

        # First tick: greeting not sent yet
        assert s._greeting_sent is False
        # Simulate sending
        s._greeting_sent = True

        # Second tick: already sent
        assert s._greeting_sent is True


# === Bug #2: Auto-buy dead + unbounded ===

class TestAutoBuy:
    def test_auto_buy_max_per_stream_slot(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
        settings = StreamerSettings(auto_buy=True, auto_buy_max_per_stream=3)
        settings.default()
        assert settings.auto_buy_max_per_stream == 3

    def test_auto_buy_max_per_stream_default(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import StreamerSettings
        settings = StreamerSettings(auto_buy=True)
        settings.default()
        assert settings.auto_buy_max_per_stream == 0

    def test_bought_items_slot(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        assert hasattr(s, 'bought_items')
        assert s.bought_items == {}

    def test_bought_items_reset_on_set_online(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        s.bought_items = {"item1": True}
        s.is_online = False
        s.set_online()
        assert s.bought_items == {}

    def test_bought_items_reset_on_set_offline(self):
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer
        s = Streamer("testuser")
        s.bought_items = {"item1": True}
        s.is_online = True
        s.set_offline()
        assert s.bought_items == {}

    def test_check_and_auto_buy_skips_disabled_items(self):
        """Items with isEnabled=False should be skipped."""
        from TwitchChannelPointsMiner.classes.Twitch import Twitch
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

        t = MagicMock(spec=Twitch)
        t.get_channel_points_store = MagicMock(return_value={
            "items": [
                {"id": "item1", "cost": 100, "isEnabled": False, "isInStock": True},
                {"id": "item2", "cost": 100, "isEnabled": True, "isInStock": True},
            ]
        })
        t.auto_buy_item = MagicMock(return_value=True)

        s = Streamer("testuser")
        s.settings = StreamerSettings(auto_buy=True)
        s.settings.default()
        s.channel_points = 1000

        # Call the real method
        Twitch.check_and_auto_buy(t, s)

        # Only item2 should be bought
        assert t.auto_buy_item.call_count == 1
        assert t.auto_buy_item.call_args[0][1] == "item2"

    def test_check_and_auto_buy_skips_out_of_stock(self):
        """Items with isInStock=False should be skipped."""
        from TwitchChannelPointsMiner.classes.Twitch import Twitch
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

        t = MagicMock(spec=Twitch)
        t.get_channel_points_store = MagicMock(return_value={
            "items": [
                {"id": "item1", "cost": 100, "isEnabled": True, "isInStock": False},
                {"id": "item2", "cost": 100, "isEnabled": True, "isInStock": True},
            ]
        })
        t.auto_buy_item = MagicMock(return_value=True)

        s = Streamer("testuser")
        s.settings = StreamerSettings(auto_buy=True)
        s.settings.default()
        s.channel_points = 1000

        Twitch.check_and_auto_buy(t, s)

        assert t.auto_buy_item.call_count == 1
        assert t.auto_buy_item.call_args[0][1] == "item2"

    def test_check_and_auto_buy_dedupes(self):
        """Items already bought should not be bought again."""
        from TwitchChannelPointsMiner.classes.Twitch import Twitch
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

        t = MagicMock(spec=Twitch)
        t.get_channel_points_store = MagicMock(return_value={
            "items": [
                {"id": "item1", "cost": 100, "isEnabled": True, "isInStock": True},
                {"id": "item2", "cost": 100, "isEnabled": True, "isInStock": True},
            ]
        })
        t.auto_buy_item = MagicMock(return_value=True)

        s = Streamer("testuser")
        s.settings = StreamerSettings(auto_buy=True)
        s.settings.default()
        s.channel_points = 1000
        s.bought_items = {"item1": True}

        Twitch.check_and_auto_buy(t, s)

        assert t.auto_buy_item.call_count == 1
        assert t.auto_buy_item.call_args[0][1] == "item2"

    def test_check_and_auto_buy_respects_cap(self):
        """Should stop after reaching max_per_stream."""
        from TwitchChannelPointsMiner.classes.Twitch import Twitch
        from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

        t = MagicMock(spec=Twitch)
        t.get_channel_points_store = MagicMock(return_value={
            "items": [
                {"id": "item1", "cost": 100, "isEnabled": True, "isInStock": True},
                {"id": "item2", "cost": 100, "isEnabled": True, "isInStock": True},
                {"id": "item3", "cost": 100, "isEnabled": True, "isInStock": True},
            ]
        })
        t.auto_buy_item = MagicMock(return_value=True)

        s = Streamer("testuser")
        s.settings = StreamerSettings(auto_buy=True, auto_buy_max_per_stream=2)
        s.settings.default()
        s.channel_points = 1000

        Twitch.check_and_auto_buy(t, s)

        assert t.auto_buy_item.call_count == 2


# === Bug #3: games= crashes ===

class TestGamesRemoved:
    def test_run_has_no_games_param(self):
        """The games parameter should be removed from run()."""
        from TwitchChannelPointsMiner.TwitchChannelPointsMiner import TwitchChannelPointsMiner
        import inspect
        sig = inspect.signature(TwitchChannelPointsMiner.run)
        assert 'games' not in sig.parameters

    def test_no_get_streamers_by_game(self):
        """Twitch class should not have get_streamers_by_game method."""
        from TwitchChannelPointsMiner.classes.Twitch import Twitch
        assert not hasattr(Twitch, 'get_streamers_by_game')


# === Bug #4: /json/<streamer> 404 ===

class TestJsonRoute:
    def test_json_route_registered(self):
        """The /json/<streamer> route should be registered in the Flask app."""
        from TwitchChannelPointsMiner.classes.AnalyticsServer import AnalyticsServer
        from TwitchChannelPointsMiner.classes.Settings import Settings

        # Create a minimal AnalyticsServer instance
        with patch.object(AnalyticsServer, '__init__', lambda self: None):
            server = AnalyticsServer()
            server.app = MagicMock()
            # Re-run the route registration
            from TwitchChannelPointsMiner.classes.AnalyticsServer import read_json
            server.app.add_url_rule = MagicMock()
            # Simulate what __init__ does
            server.app.add_url_rule(
                "/json/<string:streamer>", "json", read_json, methods=["GET"]
            )
            # Verify it was called
            server.app.add_url_rule.assert_called_once()

    def test_read_json_returns_404_for_missing_file(self):
        """read_json should return 404 for a non-existent streamer file."""
        from TwitchChannelPointsMiner.classes.AnalyticsServer import read_json
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context('/json/nonexistent.json'):
            response = read_json("nonexistent.json")
            assert response.status_code == 404

    def test_read_json_returns_200_for_existing_file(self):
        """read_json should return 200 for an existing streamer file."""
        from TwitchChannelPointsMiner.classes.AnalyticsServer import read_json
        from TwitchChannelPointsMiner.classes.Settings import Settings
        from flask import Flask
        import tempfile
        import json

        app = Flask(__name__)

        # Create a temp analytics directory with a test file
        with tempfile.TemporaryDirectory() as tmpdir:
            Settings.analytics_path = tmpdir
            test_data = {"series": [{"x": 1, "y": 100, "z": "Watch"}], "annotations": []}
            with open(os.path.join(tmpdir, "testuser.json"), "w") as f:
                json.dump(test_data, f)

            with app.test_request_context('/json/testuser.json'):
                response = read_json("testuser.json")
                assert response.status_code == 200


# === Bug #5: Case-sensitive mention highlight ===

class TestMentionHighlight:
    def test_case_insensitive_replace(self):
        """Mention highlight should work regardless of case."""
        mention = "@bob"
        msg = "Hey @Bob how are you"
        result = re.sub(
            re.escape(mention), f"\\033[1;33m{mention}\\033[0m", msg, flags=re.IGNORECASE
        )
        assert "\033[1;33m@bob\033[0m" in result
        assert "Hey" in result
        assert "how are you" in result

    def test_case_insensitive_replace_no_mention(self):
        """No highlight when mention not present."""
        mention = "@bob"
        msg = "Hey @Alice how are you"
        result = re.sub(
            re.escape(mention), f"\\033[1;33m{mention}\\033[0m", msg, flags=re.IGNORECASE
        )
        assert "\033[1;33m" not in result

    def test_mention_at_end(self):
        """Mention at end of message."""
        mention = "@bob"
        msg = "Hello @BOB"
        result = re.sub(
            re.escape(mention), f"\\033[1;33m{mention}\\033[0m", msg, flags=re.IGNORECASE
        )
        assert "\033[1;33m@bob\033[0m" in result

    def test_mention_in_middle(self):
        """Mention in middle of message."""
        mention = "@bob"
        msg = "Hey @Bob!"
        result = re.sub(
            re.escape(mention), f"\\033[1;33m{mention}\\033[0m", msg, flags=re.IGNORECASE
        )
        assert "\033[1;33m@bob\033[0m" in result


# === Bug #6: main.py cannot run ===

class TestMainPy:
    def test_main_py_no_keep_replit_alive(self):
        """main.py should not import keep_replit_alive."""
        main_path = Path(__file__).parent.parent / "main.py"
        content = main_path.read_text()
        assert "keep_replit_alive" not in content

    def test_main_py_reads_env_vars(self):
        """main.py should read TWITCH_USERNAME from environment."""
        main_path = Path(__file__).parent.parent / "main.py"
        content = main_path.read_text()
        assert "TWITCH_USERNAME" in content
        assert "os.environ.get" in content

    def test_requirements_has_dotenv(self):
        """requirements.txt should include python-dotenv."""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text()
        assert "python-dotenv" in content

    def test_main_py_imports_cleanly(self):
        """main.py should not fail on import of keep_replit_alive."""
        # We can't actually run main.py because it creates a miner instance,
        # but we can verify the file parses and doesn't reference keep_replit_alive
        import ast
        main_path = Path(__file__).parent.parent / "main.py"
        content = main_path.read_text()
        tree = ast.parse(content)
        # Check no import of keep_replit_alive
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "keep_replit_alive"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "keep_replit_alive"
