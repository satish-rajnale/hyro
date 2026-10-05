import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hyro.db import Base


def uid():
    return uuid.uuid4()


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base, Timestamped):
    __tablename__ = "teams"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class SearchProject(Base, Timestamped):
    __tablename__ = "search_projects"
    __table_args__ = (Index("ix_projects_team_created", "team_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role_title: Mapped[str] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobDescriptionVersion(Base, Timestamped):
    __tablename__ = "job_description_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_projects.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class SearchCriteria(Base, Timestamped):
    __tablename__ = "search_criteria"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_projects.id"), index=True)
    jd_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_description_versions.id"))
    requirements: Mapped[dict] = mapped_column(JSONB)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    exclusions: Mapped[list] = mapped_column(JSONB, default=list)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ResearchRun(Base, Timestamped):
    __tablename__ = "research_runs"
    __table_args__ = (Index("ix_runs_project_created", "project_id", "created_at"), Index("ix_runs_status", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_projects.id"))
    criteria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_criteria.id"))
    workflow_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    sources: Mapped[list[str]] = mapped_column(ARRAY(String))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class Candidate(Base, Timestamped):
    __tablename__ = "candidates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    full_name: Mapped[str | None] = mapped_column(String(250))
    primary_email: Mapped[str | None] = mapped_column(String(320), unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text, unique=True)


class SourceResult(Base):
    __tablename__ = "source_results"
    __table_args__ = (UniqueConstraint("research_run_id", "source", "external_id"), Index("ix_source_candidate", "candidate_id"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"))
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("candidates.id"))
    source: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(300))
    profile_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    external_ats_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateProfile(Base, Timestamped):
    __tablename__ = "candidate_profiles"
    __table_args__ = (UniqueConstraint("source_result_id"), Index("ix_profiles_candidate", "candidate_id"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"))
    source_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_results.id"))
    headline: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    experience: Mapped[list] = mapped_column(JSONB, default=list)
    resume_text: Mapped[str | None] = mapped_column(Text)
    normalized_data: Mapped[dict] = mapped_column(JSONB, default=dict)


class MatchEvaluation(Base, Timestamped):
    __tablename__ = "match_evaluations"
    __table_args__ = (UniqueConstraint("research_run_id", "candidate_id"), Index("ix_evaluations_ranked", "research_run_id", "match_score"), CheckConstraint("match_score >= 0 AND match_score <= 100"), CheckConstraint("confidence >= 0 AND confidence <= 1"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    research_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_runs.id"))
    criteria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_criteria.id"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"))
    match_score: Mapped[float] = mapped_column(Numeric(5, 2))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    score_breakdown: Mapped[dict] = mapped_column(JSONB)
    matched_requirements: Mapped[list] = mapped_column(JSONB)
    missing_requirements: Mapped[list] = mapped_column(JSONB)
    reasoning: Mapped[str] = mapped_column(Text)
    scoring_version: Mapped[str] = mapped_column(String(40))


class ShortlistDecision(Base):
    __tablename__ = "shortlist_decisions"
    __table_args__ = (UniqueConstraint("project_id", "candidate_id"), Index("ix_shortlist_project_decision", "project_id", "decision"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_projects.id"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.id"))
    decided_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
