"""How a message is delivered. Today only e-mail; SMS (or anything else) is one more class here and one more entry in CHANNELS, with no change to
audiences, messages, rules or the send loop. A channel gets an address (an e-mail address for e-mail, a number for SMS) and the finished content."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.email.service import get_email_service


class Channel(ABC):
    key: str

    @abstractmethod
    def send(self, *, to: str, subject: str, html: str, text: str, headers: dict[str, str] | None, attachments: list[dict] | None) -> None: ...


class EmailChannel(Channel):
    key = "email"

    def send(self, *, to: str, subject: str, html: str, text: str, headers: dict[str, str] | None, attachments: list[dict] | None) -> None:
        get_email_service().send_email(to=to, subject=subject, html=html, text=text, attachments=attachments, headers=headers)


CHANNELS: dict[str, Channel] = {"email": EmailChannel()}


def get_channel(key: str) -> Channel:
    return CHANNELS[key]
