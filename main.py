# -*- coding: utf-8 -*-

from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode
from TwitchChannelPointsMiner.classes.Settings import Priority, Events, FollowersOrder
from TwitchChannelPointsMiner.classes.Pushover import Pushover
from TwitchChannelPointsMiner.classes.Matrix import Matrix
from TwitchChannelPointsMiner.classes.Telegram import Telegram
from TwitchChannelPointsMiner.classes.Webhook import Webhook
from TwitchChannelPointsMiner.classes.Discord import Discord
from TwitchChannelPointsMiner.classes.Chat import ChatPresence
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from colorama import Fore
import logging
import keep_replit_alive
import os
from dotenv import load_dotenv
load_dotenv()
username = os.getenv("TWITCH_USERNAME")
password = os.getenv("TWITCH_PASSWORD")
telech = os.getenv("TELEGRAM_CHAT_ID")
discord = os.getenv("DISCORD_WEBHOOK")
telegram = os.getenv("TELEGRAM_TOKEN")
pushoverkey = os.getenv("PUSHOVER_USER_KEY")
pushovertoken = os.getenv("PUSHOVER_TOKEN")
twitch_miner = TwitchChannelPointsMiner(
    username=username,
    # If no password will be provided, the script will ask interactively
    password=password,
    # If you want to auto claim all drops from Twitch inventory on the startup
    claim_drops_startup=True,
    priority=[                                  # Custom priority in this case for example:
        # - We want first of all to catch all watch streak from all streamers
        Priority.STREAK,
        # - When we don't have anymore watch streak to catch, wait until all drops are collected over the streamers
        Priority.DROPS,
        # - When we have all of the drops claimed and no watch-streak available, use the order priority (POINTS_ASCENDING, POINTS_DESCEDING)
        Priority.ORDER
    ],
    # Disables Analytics if False. Disabling it significantly reduces memory consumption
    enable_analytics=True,
    # Set to True at your own risk and only to fix SSL: CERTIFICATE_VERIFY_FAILED error
    disable_ssl_cert_verification=False,
    # Set to True if you want to check for your nickname mentions in the chat even without @ sign
    disable_at_in_nickname=False,
    logger_settings=LoggerSettings(
        # If you want to save logs in a file (suggested)
        save=True,
        # Level of logs - use logging.DEBUG for more info
        console_level=logging.INFO,
        # Adds a username to every console log line if True. Also adds it to Telegram, Discord, etc. Useful when you have several accounts
        console_username=False,
        # Create a file rotation handler with interval = 1D and backupCount = 7 if True (default)
        auto_clear=True,
        # Set a specific time zone for console and file loggers. Use tz database names. Example: "America/Denver"
        time_zone="",
        # Level of logs - If you think the log file it's too big, use logging.INFO
        file_level=logging.DEBUG,
        # On Windows, we have a problem printing emoji. Set to false if you have a problem
        emoji=True,
        # If you think that the logs are too verbose, set this to True
        less=True,
        colored=True,                           # If you want to print colored text
        color_palette=ColorPalette(             # You can also create a custom palette color (for the common message).
            # Don't worry about lower/upper case. The script will parse all the values.
            STREAMER_online="GREEN",
            streamer_offline="red",             # Read more in README.md
            # Color allowed are: [BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET].
            BET_wiN=Fore.MAGENTA
        ),
        telegram=Telegram(                                                          # You can omit or set to None if you don't want to receive updates on Telegram
            # Chat ID to send messages @getmyid_bot
            chat_id=telech,
            # Telegram API token @BotFather
            token=telegram,
            events=[Events.BET_START, Events.BET_LOSE, Events.CHAT_MENTION, Events.BET_WIN, Events.JOIN_RAID,
                    Events.STREAMER_ONLINE, Events.GAIN_FOR_RAID, Events.GAIN_FOR_CLAIM,
                    Events.GAIN_FOR_WATCH],
            # Revoke the notification (sound/vibration)
            disable_notification=True,
        ),
        discord=Discord(
            # Discord Webhook URL
            webhook_api=discord,
            events=[Events.BET_START, Events.BET_LOSE, Events.CHAT_MENTION, Events.BET_WIN, Events.JOIN_RAID,
                    Events.STREAMER_ONLINE, Events.GAIN_FOR_RAID, Events.GAIN_FOR_CLAIM,
                    Events.GAIN_FOR_WATCH],
        ),
        webhook=Webhook(
            # Webhook URL
            endpoint="https://example.com/webhook",
            # GET or POST
            method="GET",
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                    # Only these events will be sent to the endpoint
                    Events.BET_LOSE, Events.CHAT_MENTION],
        ),
        matrix=Matrix(
            # Matrix username (without homeserver)
            username="twitch_miner",
            # Matrix password
            password="...",
            # Matrix homeserver
            homeserver="matrix.org",
            # Room ID
            room_id="...",
            events=[Events.STREAMER_ONLINE, Events.STREAMER_OFFLINE,
                    Events.BET_LOSE],  # Only these events will be sent
        ),
        pushover=Pushover(
            # Login to https://pushover.net/, the user token is on the main page
            userkey=pushoverkey,
            # Create a application on the website, and use the token shown in your application
            token=pushovertoken,
            # Read more about priority here: https://pushover.net/api#priority
            priority=0,
            # A list of sounds can be found here: https://pushover.net/api#sounds
            sound="pushover",
            # Only these events will be sent
            events=[Events.CHAT_MENTION, Events.DROP_CLAIM],
        )
    ),
    streamer_settings=StreamerSettings(
        make_predictions=True,                  # If you want to Bet / Make prediction
        follow_raid=True,                       # Follow raid to obtain more points
        # We can't filter rewards base on stream. Set to False for skip viewing counter increase and you will never obtain a drop reward from this script. Issue #21
        claim_drops=True,
        # If set to True, https://help.twitch.tv/s/article/moments will be claimed when available
        claim_moments=True,
        # If a streamer go online change the priority of streamers array and catch the watch screak. Issue #11
        watch_streak=True,
        # Join irc chat to increase watch-time [ALWAYS, NEVER, ONLINE, OFFLINE]
        chat=ChatPresence.ONLINE,
        bet=BetSettings(
            strategy=Strategy.SMART,            # Choose you strategy!
            percentage=5,                       # Place the x% of your channel points
            # Gap difference between outcomesA and outcomesB (for SMART strategy)
            percentage_gap=20,
            # If the x percentage of your channel points is gt bet_max_points set this value
            max_points=50000,
            # If the calculated amount of channel points is GT the highest bet, place the highest value minus 1-2 points Issue #33
            stealth_mode=True,
            # When placing a bet, we will wait until `delay` seconds before the end of the timer
            delay_mode=DelayMode.FROM_END,
            delay=6,
            # Place the bet only if we have at least 20k points. Issue #113
            minimum_points=1500,
            filter_condition=FilterCondition(
                # Where apply the filter. Allowed [PERCENTAGE_USERS, ODDS_PERCENTAGE, ODDS, TOP_POINTS, TOTAL_USERS, TOTAL_POINTS]
                by=OutcomeKeys.TOTAL_USERS,
                # 'by' must be [GT, LT, GTE, LTE] than value
                where=Condition.LTE,
                value=800
            )
        )
    )
)

# You can customize the settings for each streamer. If not settings were provided, the script would use the streamer_settings from TwitchChannelPointsMiner.
# If no streamer_settings are provided in TwitchChannelPointsMiner the script will use default settings.
# The streamers array can be a String -> username or Streamer instance.

# The settings priority are: settings in mine function, settings in TwitchChannelPointsMiner instance, default settings.
# For example, if in the mine function you don't provide any value for 'make_prediction' but you have set it on TwitchChannelPointsMiner instance, the script will take the value from here.
# If you haven't set any value even in the instance the default one will be used

# Start the Analytics web-server
twitch_miner.analytics(host="127.0.0.1", port=5000, refresh=5, days_ago=7)

twitch_miner.mine(
    # Array of streamers (order = priority)
    [],
    followers=True,                    # Automatic download the list of your followers
    # Sort the followers list by follow date. ASC or DESC
    followers_order=FollowersOrder.ASC
)
