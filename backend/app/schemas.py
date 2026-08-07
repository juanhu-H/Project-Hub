from typing import Any, Literal
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)


class ArtifactInput(BaseModel):
    artifact_type: Literal["jira", "endpoint", "document", "test", "decision", "transcript"]
    external_id: str
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranscriptInput(BaseModel):
    title: str
    content: str


class RelationDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = ""


class FeedbackInput(BaseModel):
    target_type: str
    target_id: str
    outcome: Literal["accepted", "rejected", "successful", "failed"]
    comment: str = ""
