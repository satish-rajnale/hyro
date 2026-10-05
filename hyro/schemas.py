from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FromORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    role_title: str = Field(min_length=2, max_length=250)


class ProjectOut(FromORM):
    id: UUID
    role_title: str
    status: str
    created_at: datetime


class JDCreate(BaseModel):
    content: str = Field(min_length=20)
    kind: str = Field(default="original", pattern="^(original|refined)$")


class JDOut(FromORM):
    id: UUID
    project_id: UUID
    version_number: int
    kind: str
    content: str
    approved_at: datetime | None


class Requirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_years_experience: int | None = Field(default=None, ge=0, le=70)
    locations: list[str] = Field(default_factory=list)
    required_certifications: list[str] = Field(default_factory=list)


class CriteriaUpdate(BaseModel):
    requirements: Requirements
    keywords: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)


class CriteriaOut(FromORM):
    id: UUID
    project_id: UUID
    jd_version_id: UUID
    requirements: Requirements
    keywords: list[str]
    exclusions: list[str]
    approved_at: datetime | None


class SourceName(StrEnum):
    github = "github"
    naukri = "naukri"
    web = "web"


class RunCreate(BaseModel):
    criteria_id: UUID
    sources: list[SourceName] = Field(default_factory=lambda: list(SourceName), min_length=1)


class RunOut(FromORM):
    id: UUID
    project_id: UUID
    criteria_id: UUID
    workflow_id: str
    status: str
    sources: list[str]
    error_message: str | None
    created_at: datetime


class EvaluationOut(FromORM):
    candidate_id: UUID
    full_name: str | None = None
    match_score: float
    confidence: float
    score_breakdown: dict
    matched_requirements: list
    missing_requirements: list
    reasoning: str
    scoring_version: str
    source_urls: list[str] = Field(default_factory=list)


class RankedResults(BaseModel):
    total: int
    items: list[EvaluationOut]


class CandidateDetail(BaseModel):
    id: UUID
    full_name: str | None
    primary_email: str | None
    profiles: list[dict]


class DecisionValue(StrEnum):
    saved = "saved"
    rejected = "rejected"
    undecided = "undecided"


class DecisionUpdate(BaseModel):
    decision: DecisionValue
    notes: str | None = None


class DecisionOut(FromORM):
    project_id: UUID
    candidate_id: UUID
    decision: str
    notes: str | None
    updated_at: datetime
