from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    SLACK_MESSAGE = "slack_message"
    SLACK_THREAD = "slack_thread"
    HUBSPOT_DEAL = "hubspot_deal"
    HUBSPOT_CONTACT = "hubspot_contact"
    HUBSPOT_TICKET = "hubspot_ticket"
    HUBSPOT_ACTIVITY = "hubspot_activity"
    GOOGLE_DOC_EDIT = "google_doc_edit"
    GOOGLE_DOC_COMMENT = "google_doc_comment"
    NOTION_PAGE = "notion_page"
    NOTION_DB = "notion_db"
    MEETING = "meeting"


class ContentType(StrEnum):
    MESSAGE = "message"
    THREAD = "thread"
    NOTE = "note"
    EDIT = "edit"
    STAGE_CHANGE = "stage_change"
    COMMENT = "comment"
    ACTIVITY = "activity"


@runtime_checkable
class SynthesisSource(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def source_type(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def timestamp(self) -> datetime | None: ...

    @property
    def participants_list(self) -> list[str]: ...

    @property
    def content_for_synthesis(self) -> str | None: ...

    def attribution_text(self) -> str: ...


class SourceItem(BaseModel):
    id: str
    source_type: SourceType
    content_type: ContentType
    title: str
    timestamp: datetime
    content: str
    summary: str | None = None
    participants: list[str] = Field(default_factory=list)
    source_url: str
    context: dict = Field(default_factory=dict)
    display_context: str = ""
    raw_data: dict | None = None

    @property
    def source_id(self) -> str:
        return self.id

    @property
    def participants_list(self) -> list[str]:
        return self.participants

    @property
    def content_for_synthesis(self) -> str | None:
        return self.summary or self.content

    def attribution_text(self) -> str:
        if self.display_context:
            return f"(per {self.display_context})"
        return f"(per {self.source_type.value})"
