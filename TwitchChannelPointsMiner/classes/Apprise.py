import logging
import requests

from TwitchChannelPointsMiner.classes.Settings import Events, Settings

logger = logging.getLogger(__name__)


class Apprise:
    def __init__(self, urls, events=None):
        """
        Apprise notification support.
        :param urls: Comma-separated list of Apprise URLs (e.g., "json://localhost", "discord://webhook_id/webhook_token")
        :param events: List of Events to trigger notifications
        """
        self.urls = [url.strip() for url in urls.split(",") if url.strip()]
        self.events = events or [
            Events.STREAMER_ONLINE,
            Events.STREAMER_OFFLINE,
            Events.BET_LOSE,
            Events.CHAT_MENTION,
            Events.DROP_CLAIM,
        ]

    def send(self, message, event):
        if event not in self.events:
            return
        for url in self.urls:
            try:
                requests.post(url, json={"title": "Twitch Miner", "body": message}, timeout=10)
            except Exception as e:
                logger.debug(f"Apprise notification failed for {url}: {e}")
