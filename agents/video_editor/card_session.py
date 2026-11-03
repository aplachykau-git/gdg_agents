"""Persistent, per-conversation state of the speaker-card editor.

The editor keeps three independent things in session state:

* ``speaker``   – who the card is for (text fields + portrait/video). Lives for the
                  whole conversation and is NOT cleared after a render, so the user can
                  render as many variants for the same speaker as they like.
* ``scenarios`` – the latest proposed creative scenarios (for portrait images).
* ``renders``   – history of finished renders.

All mutations go through small pure helpers so the logic can be unit-tested without
Gemini, Omni or HyperFrames.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

from .workflow_models import CreativeScenario, RenderedAsset, UploadedMedia

SESSION_STATE_KEY = "video_editor_session"
UI_SELECTION_STATE_KEY = "video_editor_ui_selection"
LEGACY_DRAFT_KEYS = ("video_editor_draft", "video_editor_last_rendered_draft")


class SpeakerProfile(BaseModel):
    title: str | None = None
    name: str | None = None
    position_company: str | None = None
    speaker_bio: str | None = None
    media: UploadedMedia | None = None

    @property
    def media_kind(self) -> Literal["image", "video"] | None:
        if not self.media:
            return None
        if self.media.mime_type.startswith("image/"):
            return "image"
        if self.media.mime_type.startswith("video/"):
            return "video"
        return None

    def missing_fields(self) -> list[str]:
        fields = (
            ("talk title", self.title),
            ("speaker name", self.name),
            ("position and company", self.position_company),
            ("portrait photo or video", self.media),
        )
        return [label for label, value in fields if not value]

    def summary(self) -> dict[str, Any]:
        return {
            "talk_title": self.title,
            "name": self.name,
            "position_company": self.position_company,
            "speaker_bio": self.speaker_bio,
            "media": self.media_kind or "missing",
        }


class RenderRecord(BaseModel):
    label: str
    scenario_id: str | None = None
    creative_direction: str | None = None
    assets: list[RenderedAsset] = Field(default_factory=list)
    notice: str | None = None


class UiSelection(BaseModel):
    """A scenario choice made in the web UI deck (sent via state_delta)."""

    scenario_id: str
    style_id: str | None = None
    prompt: str | None = None
    edited: bool = False


class CardSession(BaseModel):
    speaker: SpeakerProfile = Field(default_factory=SpeakerProfile)
    creative_guidance: str | None = None
    scenarios: list[CreativeScenario] = Field(default_factory=list)
    renders: list[RenderRecord] = Field(default_factory=list)
    # Upload that must not be re-attached automatically (set when the user starts a new speaker).
    ignored_upload: UploadedMedia | None = None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.replace("\u2028", "\n").replace("\u2029", "\n\n").strip()
    return value or None


def _state_get(state: Any, key: str, default: Any = None) -> Any:
    try:
        return state.get(key, default)
    except Exception:
        return default


def load_session(state: Any) -> CardSession:
    raw = _state_get(state, SESSION_STATE_KEY)
    if isinstance(raw, Mapping) and raw:
        try:
            return CardSession.model_validate(dict(raw))
        except Exception:
            pass
    # Migrate sessions created by the old single-tool implementation.
    for key in LEGACY_DRAFT_KEYS:
        legacy = _state_get(state, key)
        if isinstance(legacy, Mapping) and legacy.get("name"):
            media = legacy.get("media")
            return CardSession(
                speaker=SpeakerProfile(
                    title=legacy.get("title"),
                    name=legacy.get("name"),
                    position_company=legacy.get("position_company"),
                    speaker_bio=legacy.get("speaker_bio"),
                    media=UploadedMedia.model_validate(media) if isinstance(media, Mapping) and media else None,
                ),
                creative_guidance=legacy.get("creative_guidance"),
                scenarios=[CreativeScenario.model_validate(s) for s in legacy.get("suggested_scenarios") or []],
            )
    return CardSession()


def save_session(state: Any, session: CardSession) -> None:
    state[SESSION_STATE_KEY] = session.model_dump(mode="json")


def pop_ui_selection(state: Any) -> UiSelection | None:
    raw = _state_get(state, UI_SELECTION_STATE_KEY)
    if not isinstance(raw, Mapping) or not raw.get("scenario_id"):
        return None
    try:
        selection = UiSelection.model_validate(dict(raw))
    except Exception:
        selection = None
    state[UI_SELECTION_STATE_KEY] = None
    return selection


def attach_latest_upload(session: CardSession, latest: UploadedMedia | None) -> bool:
    """Attach the most recent user upload unless it is already attached or explicitly ignored.

    Returns True when the media changed.
    """
    if latest is None or latest == session.speaker.media or latest == session.ignored_upload:
        return False
    session.speaker.media = latest
    session.ignored_upload = None
    return True


def update_speaker_fields(
    session: CardSession,
    *,
    title: str | None = None,
    name: str | None = None,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    new_speaker: bool = False,
    keep_media: bool = False,
) -> list[str]:
    """Apply a partial update. Returns the list of changed field names.

    ``new_speaker`` starts a card for a different person: text, scenarios and the
    previous photo are dropped (the photo is kept only when ``keep_media`` is set,
    i.e. it was uploaded together with the request for the new speaker).
    """
    changed: list[str] = []
    if new_speaker:
        previous_media = session.speaker.media
        session.speaker = SpeakerProfile(media=previous_media if keep_media else None)
        session.scenarios = []
        session.creative_guidance = None
        session.ignored_upload = None if keep_media else previous_media
        changed.append("new_speaker")
    for field, value in (
        ("title", title),
        ("name", name),
        ("position_company", position_company),
        ("speaker_bio", speaker_bio),
    ):
        value = _clean(value)
        if value is not None and value != getattr(session.speaker, field):
            setattr(session.speaker, field, value)
            changed.append(field)
    return changed
