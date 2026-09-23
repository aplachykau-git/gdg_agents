"""Lightweight stand-ins for ADK session objects used by the video-editor tests."""

from __future__ import annotations


class FakeInlineData:
    def __init__(self, mime_type: str, data: bytes):
        self.mime_type = mime_type
        self.data = data


class FakePart:
    def __init__(self, text: str | None = None, inline_data: FakeInlineData | None = None):
        self.text = text
        self.inline_data = inline_data


class FakeContent:
    def __init__(self, parts: list[FakePart]):
        self.parts = parts


class FakeEvent:
    def __init__(self, event_id: str, parts: list[FakePart], author: str = "user"):
        self.id = event_id
        self.author = author
        self.content = FakeContent(parts)


class FakeSession:
    def __init__(self, events: list[FakeEvent]):
        self.id = "test-session"
        self.events = events
        self.state: dict = {}


class FakeToolContext:
    def __init__(self, state: dict, events: list[FakeEvent]):
        self.state = state
        self.session = FakeSession(events)


def image_upload(event_id: str = "img", mime_type: str = "image/png") -> FakeEvent:
    return FakeEvent(event_id, [FakePart(inline_data=FakeInlineData(mime_type, b"image"))])


def video_upload(event_id: str = "vid") -> FakeEvent:
    return FakeEvent(event_id, [FakePart(inline_data=FakeInlineData("video/mp4", b"video"))])


def user_text(event_id: str, text: str) -> FakeEvent:
    return FakeEvent(event_id, [FakePart(text=text)])
