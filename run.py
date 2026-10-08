# -*- coding: utf-8 -*-
"""
Twitch Channel Points Miner - Run Script
=========================================
Cara pakai:
1. Isi TWITCH_USERNAME dan TWITCH_PASSWORD di file .env
2. Jalankan: python3 run.py
3. Buka http://localhost:5000 untuk lihat dashboard
"""
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

# ==================== KONFIGURASI ====================

# Username & Password Twitch (dibaca dari .env)
username = os.environ.get("TWITCH_USERNAME", "")
password = os.environ.get("TWITCH_PASSWORD", "")

if not username:
    print("Error: TWITCH_USERNAME not set in .env or environment")
    sys.exit(1)

# Streamers spesifik yang mau ditontong (kosongkan kalau mau pakai followers)
# Contoh: streamers = ["notnamiko", "shroud", "xqc"]
streamers = []

# True = mining semua followers, False = mining streamers di atas saja
use_followers = True

# ==================== PENGATURAN MINER ====================

twitch_miner = TwitchChannelPointsMiner(
    username=username,
    password=password,

    # Auto-claim semua drops yang sudah selesai saat startup
    claim_drops_startup=True,

    # Enable analytics dashboard (http://localhost:5000)
    enable_analytics=True,

    # Prioritas mining: Streak > Drops > Order (urutan followers)
    priority=[Priority.STREAK, Priority.DROPS, Priority.ORDER],

    # Pengaturan log
    logger_settings=LoggerSettings(
        save=True,              # Simpan log ke file
        console_level=20,       # INFO (10=DEBUG, 20=INFO, 30=WARNING)
        less=True,              # Format log sederhana
        colored=True,           # Warna di console
    ),

    # Pengaturan streamer
    streamer_settings=StreamerSettings(
        make_predictions=False,  # True = ikut betting/prediction (butuh strategi)
        follow_raid=True,       # Ikut raid untuk bonus points
        claim_drops=True,       # Auto-claim drops
        watch_streak=True,      # Prioritaskan watch streak
        chat=ChatPresence.ONLINE,  # Join IRC chat saat streamer online
    ),
)

# ==================== JALANKAN ====================

# Start analytics server (dashboard web)
twitch_miner.analytics(host="0.0.0.0", port=5000, refresh=5, days_ago=7)

# Start mining
twitch_miner.mine(
    streamers=streamers,
    followers=use_followers,
)
