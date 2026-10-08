# -*- coding: utf-8 -*-

import logging
import os
import random
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from TwitchChannelPointsMiner.classes.Chat import ChatPresence, ThreadChat
from TwitchChannelPointsMiner.classes.entities.PubsubTopic import PubsubTopic
from TwitchChannelPointsMiner.classes.entities.Streamer import (
    Streamer,
    StreamerSettings,
)
from TwitchChannelPointsMiner.classes.Exceptions import StreamerDoesNotExistException
from TwitchChannelPointsMiner.classes.Settings import FollowersOrder, Priority, Settings
from TwitchChannelPointsMiner.classes.Twitch import Twitch
from TwitchChannelPointsMiner.classes.WebSocketsPool import WebSocketsPool
from TwitchChannelPointsMiner.logger import LoggerSettings, configure_loggers
from TwitchChannelPointsMiner.utils import (
    _millify,
    at_least_one_value_in_settings_is,
    check_versions,
    get_user_agent,
    internet_connection_available,
    set_default_settings,
)

# Suppress:
#   - chardet.charsetprober - [feed]
#   - chardet.charsetprober - [get_confidence]
#   - requests - [Starting new HTTPS connection (1)]
#   - Flask (werkzeug) logs
#   - irc.client - [process_data]
#   - irc.client - [_dispatcher]
#   - irc.client - [_handle_message]
logging.getLogger("chardet.charsetprober").setLevel(logging.ERROR)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("irc.client").setLevel(logging.ERROR)
logging.getLogger("seleniumwire").setLevel(logging.ERROR)
logging.getLogger("websocket").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class TwitchChannelPointsMiner:
    __slots__ = [
        "username",
        "twitch",
        "claim_drops_startup",
        "enable_analytics",
        "disable_ssl_cert_verification",
        "disable_at_in_nickname",
        "proxy",
        "priority",
        "streamers",
        "events_predictions",
        "minute_watcher_thread",
        "sync_campaigns_thread",
        "ws_pool",
        "session_id",
        "running",
        "start_datetime",
        "original_streamers",
        "logs_file",
        "queue_listener",
        "_pending_additions",
        "_pending_removals",
    ]

    def __init__(
        self,
        username: str,
        password: str = None,
        claim_drops_startup: bool = False,
        enable_analytics: bool = False,
        disable_ssl_cert_verification: bool = False,
        disable_at_in_nickname: bool = False,
        proxy: str = None,
        # Settings for logging and selenium as you can see.
        priority: list = [Priority.STREAK, Priority.DROPS, Priority.ORDER],
        # This settings will be global shared trought Settings class
        logger_settings: LoggerSettings = LoggerSettings(),
        # Default values for all streamers
        streamer_settings: StreamerSettings = StreamerSettings(),
    ):
        # Fixes TypeError: 'NoneType' object is not subscriptable
        if not username or username == "your-twitch-username":
            logger.error("Please edit your runner file (usually run.py) and try again.")
            logger.error("No username, exiting...")
            sys.exit(0)

        # This disables certificate verification and allows the connection to proceed, but also makes it vulnerable to man-in-the-middle (MITM) attacks.
        Settings.disable_ssl_cert_verification = disable_ssl_cert_verification

        Settings.disable_at_in_nickname = disable_at_in_nickname

        # #618: Configurable max watch amount (default: 2, Twitch limit)
        Settings.max_watch_amount = 2

        # Store miner instance for AnalyticsServer access
        Settings._miner_instance = self

        self.proxy = proxy

        import socket

        def is_connected():
            try:
                # resolve the IP address of the Twitch.tv domain name
                socket.gethostbyname("twitch.tv")
                return True
            except OSError:
                pass
            return False

        # check for Twitch.tv connectivity every 5 seconds
        error_printed = False
        while not is_connected():
            if not error_printed:
                logger.error("Waiting for Twitch.tv connectivity...")
                error_printed = True
            time.sleep(5)

        # Analytics switch
        Settings.enable_analytics = enable_analytics

        if enable_analytics is True:
            Settings.analytics_path = os.path.join(
                Path().absolute(), "analytics", username
            )
            Path(Settings.analytics_path).mkdir(parents=True, exist_ok=True)

        self.username = username

        # Set as global config
        Settings.logger = logger_settings

        # Init as default all the missing values
        streamer_settings.default()
        streamer_settings.bet.default()
        Settings.streamer_settings = streamer_settings

        # user_agent = get_user_agent("FIREFOX")
        user_agent = get_user_agent("CHROME")
        self.twitch = Twitch(self.username, user_agent, password, proxy=self.proxy)

        self.claim_drops_startup = claim_drops_startup
        self.priority = priority if isinstance(priority, list) else [priority]

        self.streamers: list[Streamer] = []
        self.events_predictions = {}
        self.minute_watcher_thread = None
        self.sync_campaigns_thread = None
        self.ws_pool = None

        self.session_id = str(uuid.uuid4())
        self.running = False
        self.start_datetime = None
        self.original_streamers = []

        self.logs_file, self.queue_listener = configure_loggers(
            self.username, logger_settings
        )

        # Check for the latest version of the script
        current_version, github_version = check_versions()

        logger.info(
            f"Twitch Channel Points Miner v2-{current_version} (fork by rdavydov)"
        )
        logger.info("https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2")

        if github_version == "0.0.0":
            logger.error(
                "Unable to detect if you have the latest version of this script"
            )
        elif current_version != github_version:
            logger.info(f"You are running version {current_version} of this script")
            logger.info(f"The latest version on GitHub is {github_version}")

        for sign in [signal.SIGINT, signal.SIGSEGV, signal.SIGTERM]:
            signal.signal(sign, self.end)

    def analytics(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        refresh: int = 5,
        days_ago: int = 7,
    ):
        # Analytics switch
        if Settings.enable_analytics is True:
            from TwitchChannelPointsMiner.classes.AnalyticsServer import AnalyticsServer

            days_ago = days_ago if days_ago <= 365 * 15 else 365 * 15
            http_server = AnalyticsServer(
                host=host,
                port=port,
                refresh=refresh,
                days_ago=days_ago,
                username=self.username,
            )
            http_server.daemon = True
            http_server.name = "Analytics Thread"
            http_server.start()
        else:
            logger.error("Can't start analytics(), please set enable_analytics=True")

    def mine(
        self,
        streamers: list = [],
        blacklist: list = [],
        followers: bool = False,
        followers_order: FollowersOrder = FollowersOrder.ASC,
    ):
        # #784: Pass followers_order to run() to prevent TypeError
        self.run(streamers=streamers, blacklist=blacklist, followers=followers, followers_order=followers_order)

    def run(
        self,
        streamers: list = [],
        blacklist: list = [],
        followers: bool = False,
        followers_order: FollowersOrder = FollowersOrder.ASC,
        games: list = [],
    ):
        if self.running:
            logger.error("You can't start multiple sessions of this instance!")
        else:
            print(f"[DEBUG] run() called, starting session {self.session_id}", flush=True)
            logger.info(
                f"Start session: '{self.session_id}'", extra={"emoji": ":bomb:"}
            )
            self.running = True
            self.start_datetime = datetime.now()

            self.twitch.login()

            if self.claim_drops_startup is True:
                self.twitch.claim_all_drops_from_inventory()

            streamers_name: list = []
            streamers_dict: dict = {}

            for streamer in streamers:
                username = (
                    streamer.username
                    if isinstance(streamer, Streamer)
                    else streamer.lower().strip()
                )
                if username not in blacklist:
                    streamers_name.append(username)
                    streamers_dict[username] = streamer

            if followers is True:
                followers_array = self.twitch.get_followers(order=followers_order)
                logger.info(
                    f"Load {len(followers_array)} followers from your profile!",
                    extra={"emoji": ":clipboard:"},
                )
                for username in followers_array:
                    if username not in streamers_dict and username not in blacklist:
                        streamers_name.append(username)
                        streamers_dict[username] = username.lower().strip()

            # #621: Mine by game category instead of by streamer name
            if games:
                game_streamers = self.twitch.get_streamers_by_game(games)
                logger.info(
                    f"Found {len(game_streamers)} streamers for games: {', '.join(games)}",
                    extra={"emoji": ":video_game:"},
                )
                for username in game_streamers:
                    if username not in streamers_dict and username not in blacklist:
                        streamers_name.append(username)
                        streamers_dict[username] = username.lower().strip()

            logger.info(
                f"Loading data for {len(streamers_name)} streamers. Please wait...",
                extra={"emoji": ":nerd_face:"},
            )

            # #629: Asynchronously Get Streamer Data on Startup using ThreadPoolExecutor
            def _load_streamer_data(username):
                try:
                    streamer = (
                        streamers_dict[username]
                        if isinstance(streamers_dict[username], Streamer) is True
                        else Streamer(username)
                    )
                    streamer.channel_id = self.twitch.get_channel_id(username)
                    streamer.settings = set_default_settings(
                        streamer.settings, Settings.streamer_settings
                    )
                    streamer.settings.bet = set_default_settings(
                        streamer.settings.bet, Settings.streamer_settings.bet
                    )
                    if streamer.settings.chat != ChatPresence.NEVER:
                        streamer.irc_chat = ThreadChat(
                            self.username,
                            self.twitch.twitch_login.get_auth_token(),
                            streamer.username,
                            random_messages=streamer.settings.random_messages,
                            random_message_interval=streamer.settings.random_message_interval,
                        )
                    return streamer
                except StreamerDoesNotExistException:
                    logger.info(
                        f"Streamer {username} does not exist",
                        extra={"emoji": ":cry:"},
                    )
                    return None

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_username = {
                    executor.submit(_load_streamer_data, username): username
                    for username in streamers_name
                }
                for future in as_completed(future_to_username):
                    streamer = future.result()
                    if streamer is not None:
                        self.streamers.append(streamer)

            # Populate the streamers with default values.
            # 1. Load channel points and auto-claim bonus
            # 2. Check if streamers are online
            # 3. DEACTIVATED: Check if the user is a moderator. (was used before the 5th of April 2021 to deactivate predictions)
            # #779: Parallelize the second startup loop to speed up initialization
            def _hydrate_streamer(streamer):
                try:
                    time.sleep(random.uniform(0.3, 0.7))
                    self.twitch.load_channel_points_context(streamer)
                    self.twitch.check_streamer_online(streamer)
                    # self.twitch.viewer_is_mod(streamer)
                    return streamer
                except StreamerDoesNotExistException:
                    logger.info(
                        f"Streamer {streamer.username} does not exist",
                        extra={"emoji": ":cry:"},
                    )
                    return None

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_streamer = {
                    executor.submit(_hydrate_streamer, streamer): streamer
                    for streamer in self.streamers
                }
                hydrated = []
                for future in as_completed(future_to_streamer):
                    result = future.result()
                    if result is not None:
                        hydrated.append(result)
                self.streamers = hydrated

            self.original_streamers = [
                streamer.channel_points for streamer in self.streamers
            ]

            # #639: Runtime streamer changes
            self._pending_additions = []
            self._pending_removals = []

            # If we have at least one streamer with settings = make_predictions True
            make_predictions = at_least_one_value_in_settings_is(
                self.streamers, "make_predictions", True
            )

            # If we have at least one streamer with settings = claim_drops True
            # Spawn a thread for sync inventory and dashboard
            if (
                at_least_one_value_in_settings_is(self.streamers, "claim_drops", True)
                is True
            ):
                self.sync_campaigns_thread = threading.Thread(
                    target=self.twitch.sync_campaigns,
                    args=(self.streamers,),
                )
                self.sync_campaigns_thread.name = "Sync campaigns/inventory"
                self.sync_campaigns_thread.start()
                time.sleep(30)

            self.minute_watcher_thread = threading.Thread(
                target=self.twitch.send_minute_watched_events,
                args=(self.streamers, self.priority),
            )
            self.minute_watcher_thread.name = "Minute watcher"
            self.minute_watcher_thread.start()

            self.ws_pool = WebSocketsPool(
                twitch=self.twitch,
                streamers=self.streamers,
                events_predictions=self.events_predictions,
            )

            # Subscribe to community-points-user. Get update for points spent or gains
            user_id = self.twitch.twitch_login.get_user_id()
            # print(f"!!!!!!!!!!!!!! USER_ID: {user_id}")

            # Fixes 'ERR_BADAUTH'
            if not user_id:
                logger.error("No user_id, exiting...")
                self.end(0, 0)

            self.ws_pool.submit(
                PubsubTopic(
                    "community-points-user-v1",
                    user_id=user_id,
                )
            )

            # Going to subscribe to predictions-user-v1. Get update when we place a new prediction (confirm)
            if make_predictions is True:
                self.ws_pool.submit(
                    PubsubTopic(
                        "predictions-user-v1",
                        user_id=user_id,
                    )
                )

            for streamer in self.streamers:
                self.ws_pool.submit(
                    PubsubTopic("video-playback-by-id", streamer=streamer)
                )

                if streamer.settings.follow_raid is True:
                    self.ws_pool.submit(PubsubTopic("raid", streamer=streamer))

                if streamer.settings.make_predictions is True:
                    self.ws_pool.submit(
                        PubsubTopic("predictions-channel-v1", streamer=streamer)
                    )

                if streamer.settings.claim_moments is True:
                    self.ws_pool.submit(
                        PubsubTopic("community-moments-channel-v1", streamer=streamer)
                    )

                if streamer.settings.community_goals is True:
                    self.ws_pool.submit(
                        PubsubTopic("community-points-channel-v1", streamer=streamer)
                    )

            refresh_context = time.time()
            while self.running:
                print(f"[DEBUG] Loop iteration: running={self.running}, streamers={len(self.streamers)}", flush=True)
                time.sleep(random.uniform(20, 60))

                # #639: Add/remove streamer on runtime
                # Process pending streamer additions/removals
                self.__process_runtime_streamer_changes()

                # #730: Send random chat messages
                for streamer in self.streamers:
                    if (
                        streamer.irc_chat is not None
                        and streamer.settings.chat != ChatPresence.NEVER
                        and streamer.settings.random_messages
                    ):
                        streamer.irc_chat.send_random_message()

                # #654: Send greeting message when streamer comes online
                for streamer in self.streamers:
                    if (
                        streamer.irc_chat is not None
                        and streamer.settings.greeting_message
                        and streamer.is_online
                    ):
                        if getattr(streamer, '_greeting_sent', False) is False:
                            streamer.irc_chat.send_greeting(streamer.settings.greeting_message)

                # Auto-redeem channel point rewards (emotes)
                try:
                    for streamer in self.streamers:
                        if (
                            streamer.is_online
                            and streamer.settings.auto_redeem_rewards is True
                            and streamer.channel_points > 0
                        ):
                            unlocked = self.twitch.redeem_all_rewards(streamer)
                            if unlocked > 0:
                                streamer.unlocked_rewards += unlocked
                except Exception as e:
                    logger.error(f"Auto-redeem error: {e}")

                # #794: Auto buy channel points items
                for streamer in self.streamers:
                    if streamer.is_online and streamer.settings.auto_buy is True:
                        self.twitch.check_and_auto_buy(streamer)

                # Do an external control for WebSocket. Check if the thread is running
                # Check if is not None because maybe we have already created a new connection on array+1 and now index is None
                for index in range(0, len(self.ws_pool.ws)):
                    if (
                        self.ws_pool.ws[index].is_reconnecting is False
                        and self.ws_pool.ws[index].elapsed_last_ping() > 10
                        and internet_connection_available() is True
                    ):
                        logger.info(
                            f"#{index} - The last PING was sent more than 10 minutes ago. Reconnecting to the WebSocket..."
                        )
                        WebSocketsPool.handle_reconnection(self.ws_pool.ws[index])

                if ((time.time() - refresh_context) // 60) >= 30:
                    refresh_context = time.time()
                    for index in range(0, len(self.streamers)):
                        if self.streamers[index].is_online:
                            self.twitch.load_channel_points_context(
                                self.streamers[index]
                            )

    def end(self, signum, frame):
        if not self.running:
            return
        
        logger.info("CTRL+C Detected! Please wait just a moment!")

        for streamer in self.streamers:
            if (
                streamer.irc_chat is not None
                and streamer.settings.chat != ChatPresence.NEVER
            ):
                streamer.leave_chat()
                if streamer.irc_chat.is_alive() is True:
                    streamer.irc_chat.join()

        self.running = self.twitch.running = False
        if self.ws_pool is not None:
            self.ws_pool.end()

        if self.minute_watcher_thread is not None:
            self.minute_watcher_thread.join()

        if self.sync_campaigns_thread is not None:
            self.sync_campaigns_thread.join()

        # Check if all the mutex are unlocked.
        # Prevent breaks of .json file
        for streamer in self.streamers:
            if streamer.mutex.locked():
                streamer.mutex.acquire()
                streamer.mutex.release()

        self.__print_report()

        # Stop the queue listener to make sure all messages have been logged
        self.queue_listener.stop()

        sys.exit(0)

    def add_streamer(self, streamer):
        """#639: Add a streamer at runtime."""
        if isinstance(streamer, str):
            streamer = Streamer(streamer)
        self._pending_additions.append(streamer)

    def remove_streamer(self, username):
        """#639: Remove a streamer at runtime."""
        self._pending_removals.append(username.lower().strip())

    def __process_runtime_streamer_changes(self):
        """#639: Process pending streamer additions and removals."""
        # Process removals
        for username in self._pending_removals:
            for i, s in enumerate(self.streamers):
                if s.username == username:
                    logger.info(f"Removing streamer {username} at runtime")
                    if s.irc_chat is not None:
                        s.leave_chat()
                    self.streamers.pop(i)
                    break
        self._pending_removals.clear()

        # Process additions
        for streamer in self._pending_additions:
            username = streamer.username
            # Check if already exists
            if any(s.username == username for s in self.streamers):
                continue
            try:
                streamer.channel_id = self.twitch.get_channel_id(username)
                streamer.settings = set_default_settings(
                    streamer.settings, Settings.streamer_settings
                )
                streamer.settings.bet = set_default_settings(
                    streamer.settings.bet, Settings.streamer_settings.bet
                )
                if streamer.settings.chat != ChatPresence.NEVER:
                    streamer.irc_chat = ThreadChat(
                        self.username,
                        self.twitch.twitch_login.get_auth_token(),
                        streamer.username,
                        random_messages=streamer.settings.random_messages,
                        random_message_interval=streamer.settings.random_message_interval,
                    )
                self.twitch.load_channel_points_context(streamer)
                self.twitch.check_streamer_online(streamer)
                self.streamers.append(streamer)
                logger.info(f"Added streamer {username} at runtime")
            except Exception as e:
                logger.error(f"Failed to add streamer {username}: {e}")
        self._pending_additions.clear()

    def __print_report(self):
        print("\n")
        logger.info(
            f"Ending session: '{self.session_id}'", extra={"emoji": ":stop_sign:"}
        )
        if self.logs_file is not None:
            logger.info(
                f"Logs file: {self.logs_file}", extra={"emoji": ":page_facing_up:"}
            )
        logger.info(
            f"Duration {datetime.now() - self.start_datetime}",
            extra={"emoji": ":hourglass:"},
        )

        if not Settings.logger.less and self.events_predictions != {}:
            print("")
            for event_id in self.events_predictions:
                event = self.events_predictions[event_id]
                if (
                    event.bet_confirmed is True
                    and event.streamer.settings.make_predictions is True
                ):
                    logger.info(
                        f"{event.streamer.settings.bet}",
                        extra={"emoji": ":wrench:"},
                    )
                    if event.streamer.settings.bet.filter_condition is not None:
                        logger.info(
                            f"{event.streamer.settings.bet.filter_condition}",
                            extra={"emoji": ":pushpin:"},
                        )
                    logger.info(
                        f"{event.print_recap()}",
                        extra={"emoji": ":bar_chart:"},
                    )

        print("")
        for streamer_index in range(0, len(self.streamers)):
            if self.streamers[streamer_index].history != {}:
                gained = (
                    self.streamers[streamer_index].channel_points
                    - self.original_streamers[streamer_index]
                )
                
                from colorama import Fore
                streamer_highlight = Fore.YELLOW
                
                streamer_gain = (
                    f"{streamer_highlight}{self.streamers[streamer_index]}{Fore.RESET}, Total Points Gained: {_millify(gained)}"
                    if Settings.logger.less
                    else f"{streamer_highlight}{repr(self.streamers[streamer_index])}{Fore.RESET}, Total Points Gained (after farming - before farming): {_millify(gained)}"
                )
                
                indent = ' ' * 25
                streamer_history = '\n'.join(f"{indent}{history}" for history in self.streamers[streamer_index].print_history().split('; ')) 
                
                logger.info(
                    f"{streamer_gain}\n{streamer_history}",
                    extra={"emoji": ":moneybag:"},
                )

        # #797: Monthly and Yearly Recap
        self.__print_monthly_yearly_recap()

    def __print_monthly_yearly_recap(self):
        """Print monthly and yearly recap of points gained."""
        from collections import defaultdict
        monthly = defaultdict(int)
        yearly = defaultdict(int)
        for streamer in self.streamers:
            for reason, data in streamer.history.items():
                # We don't have timestamps in history, so we use session start as reference
                # This is a simplified recap based on session data
                now = datetime.now()
                monthly[now.strftime("%Y-%m")] += data["amount"]
                yearly[now.strftime("%Y")] += data["amount"]

        print("")
        logger.info("=== Monthly Recap ===", extra={"emoji": ":calendar:"})
        for month, points in sorted(monthly.items()):
            logger.info(f"  {month}: {_millify(points)} points", extra={"emoji": ":calendar:"})

        logger.info("=== Yearly Recap ===", extra={"emoji": ":date:"})
        for year, points in sorted(yearly.items()):
            logger.info(f"  {year}: {_millify(points)} points", extra={"emoji": ":date:"})