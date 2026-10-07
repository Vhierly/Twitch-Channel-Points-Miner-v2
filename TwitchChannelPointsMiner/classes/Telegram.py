from textwrap import dedent

import requests

from TwitchChannelPointsMiner.classes.Settings import Events


class Telegram(object):
    __slots__ = ["chat_id", "telegram_api", "events", "disable_notification", "message_thread_id"]

    def __init__(
        self, chat_id: int, token: str, events: list, disable_notification: bool = False,
        message_thread_id: int = None
    ):
        self.chat_id = chat_id
        self.telegram_api = f"https://api.telegram.org/bot{token}/sendMessage"
        self.events = [str(e) for e in events]
        self.disable_notification = disable_notification
        self.message_thread_id = message_thread_id

    def send(self, message: str, event: Events) -> None:
        if str(event) in self.events:
            data = {
                "chat_id": self.chat_id,
                "text": dedent(message),
                "disable_web_page_preview": True,  # include link to twitch streamer?
                "disable_notification": self.disable_notification,  # no sound, notif just in tray
            }
            if self.message_thread_id is not None:
                data["message_thread_id"] = self.message_thread_id
            requests.post(
                url=self.telegram_api,
                data=data,
            )
