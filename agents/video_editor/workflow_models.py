from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VideoEditorRequest(BaseModel):
    title: str | None = None
    name: str | None = None
    position_company: str | None = None
    creative_direction: str | None = None
    speaker_bio: str | None = None
    creative_guidance: str | None = None


class IntakeDecision(BaseModel):
    intent: Literal["collect_details", "answer_question"] = "collect_details"
    title: str | None = None
    name: str | None = None
    position_company: str | None = None
    creative_direction: str | None = None
    user_message: str = ""


class ReviewDecision(BaseModel):
    has_human_face: bool = True
    approved: bool = True
    comment: str = ""


class ValidationFailure(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: Literal[
        "missing_field",
        "field_too_long",
        "media_not_found",
        "unsupported_media",
        "invalid_image",
        "invalid_video",
        "face_not_detected",
        "render_environment_unavailable",
        "model_unavailable",
        "render_failed",
    ]
    field: str | None = None
    message: str
    retryable: bool = True
    requested_action: Literal["correct_text", "replace_media", "retry", "retry_render"] = "retry"


class ValidatedMetadata(BaseModel):
    title: str
    name: str
    position_company: str


class ResolvedMedia(BaseModel):
    source_path: str
    media_type: Literal["image", "video", "unknown"]
    placeholder_used: bool = False


class UploadedMedia(BaseModel):
    event_id: str
    part_index: int
    mime_type: str


class VideoShot(BaseModel):
    shot_number: int
    time_range: str
    action: str
    camera: str
    lighting_atmosphere: str


class ScenarioStyle(BaseModel):
    id: str
    name: str
    genre: str
    shots: list[VideoShot] = Field(default_factory=list)
    omni_prompt: str


class CreativeScenario(BaseModel):
    id: str
    title: str
    genre: str
    concept: str
    shots: list[VideoShot] = Field(default_factory=list)
    omni_prompt: str
    styles: list[ScenarioStyle] = Field(default_factory=list)
    narrative_metaphor: str | None = None


class VideoEditorDraft(VideoEditorRequest):
    media: UploadedMedia | None = None
    confirmed_fingerprint: str | None = None
    suggested_scenarios: list[CreativeScenario] = Field(default_factory=list)
    selected_scenario_id: str | None = None


class PreparedMedia(BaseModel):
    media_type: Literal["image", "video"]
    source_path: str
    working_path: str
    video_path: str
    duration_seconds: int


class RenderedAsset(BaseModel):
    label: str
    url: str | None = None
    availability: Literal["available", "unavailable"] = "available"
    unavailable_reason: str | None = None


class VideoCardToolResult(BaseModel):
    status: Literal["success", "error", "awaiting_confirmation", "awaiting_scenario_selection"]
    code: str | None = None
    message: str
    retryable: bool = True
    requested_action: (
        Literal[
            "provide_details",
            "replace_media",
            "correct_text",
            "confirm_render",
            "select_scenario",
            "retry",
        ]
        | None
    ) = None
    missing_fields: list[str] = Field(default_factory=list)
    scenarios: list[CreativeScenario] = Field(default_factory=list)
    assets: list[RenderedAsset] = Field(default_factory=list)
    draft: VideoEditorDraft | None = None


class RenderResult(BaseModel):
    status: str
    assets: list[RenderedAsset] = Field(default_factory=list)
    summary: str
    notice: str | None = None
