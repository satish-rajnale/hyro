import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from temporalio import activity

from hyro.db import SessionLocal
from hyro.models import Candidate, CandidateProfile, MatchEvaluation, ResearchRun, SearchCriteria, SourceResult
from hyro.providers import PROVIDERS, normalize
from hyro.schemas import Requirements
from hyro.scoring import score


def now():
    return datetime.now(timezone.utc)


@activity.defn
async def set_run_state(run_id: str, state: str, error: str | None = None):
    with SessionLocal.begin() as session:
        run = session.get(ResearchRun, uuid.UUID(run_id))
        run.status = state
        run.error_message = error
        if state == "running" and run.started_at is None:
            run.started_at = now()
        if state in ("completed", "failed"):
            run.completed_at = now()


@activity.defn
async def build_queries(run_id: str) -> dict[str, str]:
    with SessionLocal() as session:
        run = session.get(ResearchRun, uuid.UUID(run_id))
        criteria = session.get(SearchCriteria, run.criteria_id)
        terms = criteria.keywords or criteria.requirements.get("required_skills", [])
        query = " ".join(terms)
        return {source: query for source in run.sources}


@activity.defn
async def fetch_provider(run_id: str, source: str, query: str) -> int:
    provider = PROVIDERS[source]
    cursor = 0
    details = activity.info().heartbeat_details
    if details:
        checkpoint = details[0]
        if checkpoint.get("source") == source:
            cursor = checkpoint["cursor"]
    processed = cursor
    while True:
        page, next_cursor = await provider.fetch_page(query, cursor, 1)
        # Persist a page before checkpointing, so retries never lose results.
        with SessionLocal.begin() as session:
            for raw in page:
                item = normalize(source, raw)
                exists = session.scalar(select(SourceResult).where(SourceResult.research_run_id == uuid.UUID(run_id), SourceResult.source == source, SourceResult.external_id == item["external_id"]))
                if exists is None:
                    session.add(SourceResult(research_run_id=uuid.UUID(run_id), source=source, external_id=item["external_id"], profile_url=item["url"], raw_payload=raw, external_ats_score=item["ats_score"]))
        processed += len(page)
        activity.heartbeat({"source": source, "cursor": next_cursor if next_cursor is not None else cursor + len(page), "processed": processed})
        if next_cursor is None:
            return processed
        cursor = next_cursor


@activity.defn
async def normalize_results(run_id: str) -> int:
    count = 0
    with SessionLocal.begin() as session:
        results = session.scalars(select(SourceResult).where(SourceResult.research_run_id == uuid.UUID(run_id)).order_by(SourceResult.id)).all()
        for result in results:
            if result.candidate_id is not None:
                continue
            p = normalize(result.source, result.raw_payload)
            candidate = None
            if p["email"]:
                candidate = session.scalar(select(Candidate).where(Candidate.primary_email == p["email"]))
            if candidate is None:
                candidate = session.scalar(select(Candidate).where(Candidate.canonical_url == p["url"]))
            if candidate is None:
                candidate = Candidate(full_name=p["name"], primary_email=p["email"], canonical_url=p["url"])
                session.add(candidate)
                session.flush()
            result.candidate_id = candidate.id
            session.add(CandidateProfile(candidate_id=candidate.id, source_result_id=result.id, headline=p["headline"], location=p["location"], skills=p["skills"], certifications=p["certifications"], experience=[{"years": p["years"]}] if p["years"] is not None else [], resume_text=p["resume_text"], normalized_data={"years": p["years"]}))
            count += 1
    return count


@activity.defn
async def evaluate_candidates(run_id: str) -> int:
    with SessionLocal.begin() as session:
        run = session.get(ResearchRun, uuid.UUID(run_id))
        criteria = session.get(SearchCriteria, run.criteria_id)
        requirements = Requirements.model_validate(criteria.requirements)
        results = session.scalars(select(SourceResult).where(SourceResult.research_run_id == run.id, SourceResult.candidate_id.is_not(None))).all()
        grouped: dict[uuid.UUID, list[dict]] = {}
        for result in results:
            grouped.setdefault(result.candidate_id, []).append(normalize(result.source, result.raw_payload))
        for candidate_id, profiles in grouped.items():
            if session.scalar(select(MatchEvaluation).where(MatchEvaluation.research_run_id == run.id, MatchEvaluation.candidate_id == candidate_id)):
                continue
            session.add(MatchEvaluation(research_run_id=run.id, criteria_id=run.criteria_id, candidate_id=candidate_id, **score(requirements, profiles)))
        return len(grouped)
