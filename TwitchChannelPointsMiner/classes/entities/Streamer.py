import json
import logging
import os
import time
from datetime import datetime
from threading import Lock

from TwitchChannelPointsMiner.classes.Chat import ChatPresence, ThreadChat
from TwitchChannelPointsMiner.classes.entities.Bet import BetSettings, DelayMode
from TwitchChannelPointsMiner.classes.entities.Stream import Stream
from TwitchChannelPointsMiner.classes.Settings import Events, Settings
from TwitchChannelPointsMiner.constants import URL
from TwitchChannelPointsMiner.utils import _millify

logger = logging.getLogger(__name__)


class StreamerSettings(object):
    __slots__ = [
        "make_predictions",
        "follow_raid",
        "claim_drops",
        "claim_moments",
        "watch_streak",
        "community_goals",
        "bet",
        "chat",
        "random_messages",
        "random_message_interval",
        "low_priority",
        "favorite",
        "greeting_message",
        "auto_buy",
        "auto_redeem_rewards",
        "auto_redeem_max_per_stream",
        "auto_redeem_skip_sounds",
        "auto_redeem_blocklist",
        "auto_redeem_delay",
    ]

    def __init__(
        self,
        make_predictions: bool = None,
        follow_raid: bool = None,
        claim_drops: bool = None,
        claim_moments: bool = None,
        watch_streak: bool = None,
        community_goals: bool = None,
        bet: BetSettings = None,
        chat: ChatPresence = None,
        random_messages: list = None,
        random_message_interval: int = None,
        low_priority: bool = None,
        favorite: bool = None,
        greeting_message: str = None,
        auto_buy: bool = None,
        auto_redeem_rewards: bool = None,
        auto_redeem_max_per_stream: int = None,
        auto_redeem_skip_sounds: bool = None,
        auto_redeem_blocklist: list = None,
        auto_redeem_delay: float = None,
    ):
        self.make_predictions = make_predictions
        self.follow_raid = follow_raid
        self.claim_drops = claim_drops
        self.claim_moments = claim_moments
        self.watch_streak = watch_streak
        self.community_goals = community_goals
        self.bet = bet
        self.chat = chat
        self.random_messages = random_messages
        self.random_message_interval = random_message_interval
        self.low_priority = low_priority
        self.favorite = favorite
        self.greeting_message = greeting_message
        self.auto_buy = auto_buy
        self.auto_redeem_rewards = auto_redeem_rewards
        # Anti-spam: max rewards to redeem per stream (0 = unlimited)
        self.auto_redeem_max_per_stream = auto_redeem_max_per_stream
        # Skip rewards whose title/prompt look like sounds (TTS, song, sound alerts)
        self.auto_redeem_skip_sounds = auto_redeem_skip_sounds
        # Extra user keywords to never redeem (matched case-insensitively)
        self.auto_redeem_blocklist = auto_redeem_blocklist
        # Seconds to wait between consecutive redemptions (anti-spam)
        self.auto_redeem_delay = auto_redeem_delay

    def default(self):
        for name in [
            "make_predictions",
            "follow_raid",
            "claim_drops",
            "claim_moments",
            "watch_streak",
        ]:
            if getattr(self, name) is None:
                setattr(self, name, True)
        if self.community_goals is None:
            self.community_goals = False
        if self.bet is None:
            self.bet = BetSettings()
        if self.chat is None:
            self.chat = ChatPresence.ONLINE
        if self.random_messages is None:
            self.random_messages = []
        if self.random_message_interval is None:
            self.random_message_interval = 300
        if self.low_priority is None:
            self.low_priority = False
        if self.favorite is None:
            self.favorite = False
        if self.greeting_message is None:
            self.greeting_message = ""
        if self.auto_buy is None:
            self.auto_buy = False
        if self.auto_redeem_rewards is None:
            self.auto_redeem_rewards = True
        if self.auto_redeem_max_per_stream is None:
            self.auto_redeem_max_per_stream = 0
        if self.auto_redeem_skip_sounds is None:
            self.auto_redeem_skip_sounds = True
        if self.auto_redeem_blocklist is None:
            self.auto_redeem_blocklist = []
        if self.auto_redeem_delay is None:
            self.auto_redeem_delay = 5.0

    def __repr__(self):
        return f"StreamerSettings(make_predictions={self.make_predictions}, follow_raid={self.follow_raid}, claim_drops={self.claim_drops}, claim_moments={self.claim_moments}, watch_streak={self.watch_streak}, community_goals={self.community_goals}, bet={self.bet}, chat={self.chat}, random_messages={self.random_messages}, random_message_interval={self.random_message_interval}, low_priority={self.low_priority}, favorite={self.favorite}, greeting_message={self.greeting_message}, auto_buy={self.auto_buy}, auto_redeem_rewards={self.auto_redeem_rewards})"


class Streamer(object):
    __slots__ = [
        "username",
        "channel_id",
        "settings",
        "is_online",
        "stream_up",
        "online_at",
        "offline_at",
        "channel_points",
        "community_goals",
        "minute_watched_requests",
        "viewer_is_mod",
        "activeMultipliers",
        "irc_chat",
        "stream",
        "raid",
        "history",
        "streamer_url",
        "mutex",
        "unlocked_rewards",
        "redeemed_rewards",
        "last_rewards",
    ]

    def __init__(self, username, settings=None):
        self.username: str = username.lower().strip()
        self.channel_id: str = ""
        self.settings = settings
        self.is_online = False
        self.stream_up = 0
        self.online_at = 0
        self.offline_at = 0
        self.channel_points = 0
        self.community_goals = {}
        self.minute_watched_requests = None
        self.viewer_is_mod = False
        self.activeMultipliers = None
        self.irc_chat = None

        self.stream = Stream()

        self.raid = None
        self.history = {}

        self.streamer_url = f"{URL}/{self.username}"

        self.mutex = Lock()
        self.unlocked_rewards = 0
        # reward_id -> True for rewards already redeemed during the current online
        # session. Reset on each new stream so a cheap reward isn't redeemed every
        # loop iteration (which would spam the streamer and drain points).
        self.redeemed_rewards = {}
        # Last redeemed reward info per stream (for the /watch dashboard):
        # {"title": str, "cost": int, "at": epoch_seconds}
        self.last_rewards = []

    def __repr__(self):
        return f"Streamer(username={self.username}, channel_id={self.channel_id}, channel_points={_millify(self.channel_points)})"

    def __str__(self):
        return (
            f"{self.username} ({_millify(self.channel_points)} points)"
            if Settings.logger.less
            else self.__repr__()
        )

    def set_offline(self):
        if self.is_online is True:
            self.offline_at = time.time()
            self.is_online = False

        self.toggle_chat()

        logger.info(
            f"{self} is Offline!",
            extra={
                "emoji": ":sleeping:",
                "event": Events.STREAMER_OFFLINE,
            },
        )

    def set_online(self):
        if self.is_online is False:
            self.online_at = time.time()
            self.is_online = True
            # New stream session -> allow redeeming each reward once again
            self.redeemed_rewards = {}
            self.last_rewards = []
            # #825: Preserve watch streak progress if streamer was recently offline
            # Only reset streak if it's been more than 30 minutes since last offline
            # or if we haven't started watching yet
            if self.offline_at == 0 or (time.time() - self.offline_at) > 1800:
                self.stream.init_watch_streak()
            # If streamer was offline for less than 30 minutes, preserve streak progress
            # by not calling init_watch_streak() - minute_watched and watch_streak_missing
            # are retained from the previous session

        self.toggle_chat()

        logger.info(
            f"{self} is Online!",
            extra={
                "emoji": ":partying_face:",
                "event": Events.STREAMER_ONLINE,
            },
        )

    def print_history(self):
        return "; ".join(
            [
                f"{key} ({self.history[key]['counter']} times, {_millify(self.history[key]['amount'])} gained)"
                for key in sorted(self.history)
                if self.history[key]["counter"] != 0
            ]
        )

    def update_history(self, reason_code, earned, counter=1):
        if reason_code not in self.history:
            self.history[reason_code] = {"counter": 0, "amount": 0}
        self.history[reason_code]["counter"] += counter
        self.history[reason_code]["amount"] += earned

        if reason_code == "WATCH_STREAK":
            self.stream.watch_streak_missing = False

    def stream_up_elapsed(self):
        return self.stream_up == 0 or ((time.time() - self.stream_up) > 120)

    def drops_condition(self):
        return (
            self.settings.claim_drops is True
            and self.is_online is True
            # and self.stream.drops_tags is True
            and self.stream.campaigns_ids != []
        )

    def viewer_has_points_multiplier(self):
        return self.activeMultipliers is not None and len(self.activeMultipliers) > 0

    def total_points_multiplier(self):
        return (
            sum(
                map(
                    lambda x: x["factor"],
                    self.activeMultipliers,
                ),
            )
            if self.activeMultipliers is not None
            else 0
        )

    def get_prediction_window(self, prediction_window_seconds):
        delay_mode = self.settings.bet.delay_mode
        delay = self.settings.bet.delay
        if delay_mode == DelayMode.FROM_START:
            return min(delay, prediction_window_seconds)
        elif delay_mode == DelayMode.FROM_END:
            return max(prediction_window_seconds - delay, 0)
        elif delay_mode == DelayMode.PERCENTAGE:
            return prediction_window_seconds * delay
        else:
            return prediction_window_seconds

    # === ANALYTICS === #
    def persistent_annotations(self, event_type, event_text):
        event_type = event_type.upper()
        if event_type in ["WATCH_STREAK", "WIN", "PREDICTION_MADE", "LOSE"]:
            primary_color = (
                "#45c1ff"  # blue #45c1ff yellow #ffe045 green #36b535 red #ff4545
                if event_type == "WATCH_STREAK"
                else (
                    "#ffe045"
                    if event_type == "PREDICTION_MADE"
                    else ("#36b535" if event_type == "WIN" else "#ff4545")
                )
            )
            data = {
                "borderColor": primary_color,
                "label": {
                    "style": {"color": "#000", "background": primary_color},
                    "text": event_text,
                },
            }
            self.__save_json("annotations", data)

    def persistent_series(self, event_type="Watch"):
        self.__save_json("series", event_type=event_type)

    def __save_json(self, key, data={}, event_type="Watch"):
        # https://stackoverflow.com/questions/4676195/why-do-i-need-to-multiply-unix-timestamps-by-1000-in-javascript
        now = datetime.now().replace(microsecond=0)
        data.update({"x": round(datetime.timestamp(now) * 1000)})

        if key == "series":
            data.update({"y": self.channel_points})
            if event_type is not None:
                data.update({"z": event_type.replace("_", " ").title()})

        fname = os.path.join(Settings.analytics_path, f"{self.username}.json")
        temp_fname = fname + ".temp"  # Temporary file name

        with self.mutex:
            # Create and write to the temporary file
            with open(temp_fname, "w") as temp_file:
                json_data = json.load(open(fname, "r")) if os.path.isfile(fname) else {}
                if key not in json_data:
                    json_data[key] = []
                json_data[key].append(data)
                json.dump(json_data, temp_file, indent=4)

            # Replace the original file with the temporary file
            os.replace(temp_fname, fname)

    def leave_chat(self):
        if self.irc_chat is not None:
            self.irc_chat.stop()

            # Recreate a new thread to start again
            # raise RuntimeError("threads can only be started once")
            self.irc_chat = ThreadChat(
                self.irc_chat.username,
                self.irc_chat.token,
                self.username,
            )

    def __join_chat(self):
        if self.irc_chat is not None:
            if self.irc_chat.is_alive() is False:
                self.irc_chat.start()

    def toggle_chat(self):
        if self.settings.chat == ChatPresence.ALWAYS:
            self.__join_chat()
        elif self.settings.chat != ChatPresence.NEVER:
            if self.is_online is True:
                if self.settings.chat == ChatPresence.ONLINE:
                    self.__join_chat()
                elif self.settings.chat == ChatPresence.OFFLINE:
                    self.leave_chat()
            else:
                if self.settings.chat == ChatPresence.ONLINE:
                    self.leave_chat()
                elif self.settings.chat == ChatPresence.OFFLINE:
                    self.__join_chat()

    def update_community_goal(self, community_goal):
        self.community_goals[community_goal.goal_id] = community_goal

    def delete_community_goal(self, goal_id):
        self.community_goals.pop(goal_id)
