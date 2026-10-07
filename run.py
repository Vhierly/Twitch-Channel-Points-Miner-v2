# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

# Load .env file if exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.classes.Settings import Priority
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

# Get credentials from environment
username = os.environ.get("TWITCH_USERNAME", "")
password = os.environ.get("TWITCH_PASSWORD", "")

if not username:
    print("Error: TWITCH_USERNAME not set in .env or environment")
    sys.exit(1)

# Streamers to mine
streamers = [
    # Add your streamers here
    # "streamer1",
    # "streamer2",
]

# Or use followers
use_followers = True

twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=password,
    claim_drops_startup=False,
    enable_analytics=True,  # Enable for /health endpoint
    priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER],
    logger_settings=LoggerSettings(
        save=True,
        console_level=10,  # DEBUG
        less=False,
        colored=True,
    ),
    streamer_settings=StreamerSettings(
        make_predictions=False,  # Set to True if you want to bet
        follow_raid=True,
        claim_drops=True,
        watch_streak=True,
        chat=ChatPresence.ONLINE,
    ),
)

# Start analytics server (for /health endpoint)
twitch_miner.analytics(host="0.0.0.0", port=5000, refresh=5, days_ago=7)

# Start mining
twitch_miner.mine(
    streamers=streamers,
    followers=use_followers,
)
