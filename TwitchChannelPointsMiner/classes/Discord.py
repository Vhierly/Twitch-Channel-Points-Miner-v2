import logging
from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.Settings import Events

logger = logging.getLogger(__name__)


class Discord(object):
    __slots__ = ["webhook_api", "events", "username"]

    def __init__(self, webhook_api, events: list, username: str = "Twitch Channel Points Miner"):
        # Support both single webhook (str) and multiple webhooks (list)
        if isinstance(webhook_api, str):
            self.webhook_api = [webhook_api]
        else:
            self.webhook_api = list(webhook_api)
        self.events = [str(e) for e in events]
        self.username = username

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            data = {
                "content": dedent(message),
                "username": self.username,
                "avatar_url": "https://i.imgur.com/X9fEkhT.png",
            }
            for webhook_url in self.webhook_api:
                try:
                    requests.post(url=webhook_url, data=data, timeout=10)
                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to send Discord notification to {webhook_url}: {e}")
