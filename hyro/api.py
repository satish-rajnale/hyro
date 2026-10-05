import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from temporalio.client import Client

from hyro.config import settings
from hyro.db import get_session
from hyro.models import Candidate, CandidateProfile, JobDescriptionVersion, MatchEvaluation, ResearchRun, SearchCriteria, SearchProject, ShortlistDecision, SourceResult, User
from hyro.schemas import CandidateDetail, CriteriaOut, CriteriaUpdate, DecisionOut, DecisionUpdate, EvaluationOut, JDCreate, JDOut, ProjectCreate, ProjectOut, RankedResults, RunCreate, RunOut
from hyro.scoring import extract_requirements
from hyro.startup import migrate_and_seed
from hyro.workflow import ResearchCandidatesWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_and_seed()
    app.state.temporal = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    yield


app = FastAPI(title="Hyro Hiring Research API", lifespan=lifespan)


def user(session: Session) -> User:
    return session.scalar(select(User).where(User.email == settings.seed_user_email))


def project_or_404(session: Session, project_id: uuid.UUID) -> SearchProject:
    project = session.get(SearchProject, project_id)
    if project is None or project.team_id != user(session).team_id:
        raise HTTPException(404, "Project not found")
    return project


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)):
    current = user(session)
    item = SearchProject(team_id=current.team_id, created_by=current.id, role_title=body.role_title)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(session: Session = Depends(get_session)):
    return session.scalars(select(SearchProject).where(SearchProject.team_id == user(session).team_id).order_by(SearchProject.created_at.desc())).all()


@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, session: Session = Depends(get_session)):
    return project_or_404(session, project_id)


@app.post("/projects/{project_id}/jds", response_model=JDOut, status_code=201)
def create_jd(project_id: uuid.UUID, body: JDCreate, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    version = (session.scalar(select(func.max(JobDescriptionVersion.version_number)).where(JobDescriptionVersion.project_id == project_id)) or 0) + 1
    jd = JobDescriptionVersion(project_id=project_id, version_number=version, kind=body.kind, content=body.content)
    session.add(jd)
    session.commit()
    session.refresh(jd)
    return jd


@app.get("/projects/{project_id}/jds", response_model=list[JDOut])
def list_jds(project_id: uuid.UUID, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    return session.scalars(select(JobDescriptionVersion).where(JobDescriptionVersion.project_id == project_id).order_by(JobDescriptionVersion.version_number)).all()


@app.post("/projects/{project_id}/jds/{jd_id}/criteria", response_model=CriteriaOut, status_code=201)
def generate_criteria(project_id: uuid.UUID, jd_id: uuid.UUID, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    jd = session.get(JobDescriptionVersion, jd_id)
    if jd is None or jd.project_id != project_id:
        raise HTTPException(404, "JD not found")
    requirements = extract_requirements(jd.content)
    item = SearchCriteria(project_id=project_id, jd_version_id=jd_id, requirements=requirements.model_dump(), keywords=requirements.required_skills, exclusions=[])
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.put("/projects/{project_id}/criteria/{criteria_id}", response_model=CriteriaOut)
def update_criteria(project_id: uuid.UUID, criteria_id: uuid.UUID, body: CriteriaUpdate, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    item = session.get(SearchCriteria, criteria_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(404, "Criteria not found")
    if item.approved_at or session.scalar(select(ResearchRun.id).where(ResearchRun.criteria_id == item.id)):
        raise HTTPException(409, "Criteria is immutable after approval or use; generate a new version")
    item.requirements = body.requirements.model_dump()
    item.keywords = body.keywords
    item.exclusions = body.exclusions
    session.commit()
    session.refresh(item)
    return item


@app.post("/projects/{project_id}/criteria/{criteria_id}/approve", response_model=CriteriaOut)
def approve_criteria(project_id: uuid.UUID, criteria_id: uuid.UUID, session: Session = Depends(get_session)):
    project = project_or_404(session, project_id)
    item = session.get(SearchCriteria, criteria_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(404, "Criteria not found")
    if item.approved_at is None:
        item.approved_at = datetime.now(timezone.utc)
        item.approved_by = user(session).id
        jd = session.get(JobDescriptionVersion, item.jd_version_id)
        jd.approved_at = item.approved_at
        jd.approved_by = item.approved_by
        project.status = "ready"
        session.commit()
    session.refresh(item)
    return item


@app.post("/projects/{project_id}/runs", response_model=RunOut, status_code=202)
async def create_run(project_id: uuid.UUID, body: RunCreate, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    criteria = session.get(SearchCriteria, body.criteria_id)
    if criteria is None or criteria.project_id != project_id or criteria.approved_at is None:
        raise HTTPException(422, "Approved criteria for this project are required")
    run_id = uuid.uuid4()
    run = ResearchRun(id=run_id, project_id=project_id, criteria_id=criteria.id, workflow_id=f"research-run-{run_id}", status="queued", sources=list(dict.fromkeys(source.value for source in body.sources)))
    session.add(run)
    session.commit()
    try:
        await app.state.temporal.start_workflow(ResearchCandidatesWorkflow.run, str(run_id), id=run.workflow_id, task_queue=settings.temporal_task_queue)
    except Exception as exc:
        run.status = "failed"
        run.error_message = f"Temporal dispatch failed: {type(exc).__name__}: {exc}"[:1000]
        run.completed_at = datetime.now(timezone.utc)
        session.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not start research workflow") from exc
    session.refresh(run)
    return run


@app.get("/projects/{project_id}/runs/{run_id}", response_model=RunOut)
def get_run(project_id: uuid.UUID, run_id: uuid.UUID, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    run = session.get(ResearchRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(404, "Run not found")
    return run


@app.get("/projects/{project_id}/runs/{run_id}/results", response_model=RankedResults)
def ranked_results(project_id: uuid.UUID, run_id: uuid.UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)):
    get_run(project_id, run_id, session)
    total = session.scalar(select(func.count()).select_from(MatchEvaluation).where(MatchEvaluation.research_run_id == run_id))
    evaluations = session.scalars(select(MatchEvaluation).where(MatchEvaluation.research_run_id == run_id).order_by(MatchEvaluation.match_score.desc(), MatchEvaluation.candidate_id).offset(offset).limit(limit)).all()
    items = []
    for evaluation in evaluations:
        candidate = session.get(Candidate, evaluation.candidate_id)
        urls = session.scalars(select(SourceResult.profile_url).where(SourceResult.research_run_id == run_id, SourceResult.candidate_id == candidate.id)).all()
        items.append(EvaluationOut.model_validate(evaluation, from_attributes=True).model_copy(update={"full_name": candidate.full_name, "source_urls": [url for url in urls if url]}))
    return RankedResults(total=total, items=items)


@app.get("/projects/{project_id}/candidates/{candidate_id}", response_model=CandidateDetail)
def candidate_detail(project_id: uuid.UUID, candidate_id: uuid.UUID, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    visible = session.scalar(select(SourceResult.id).join(ResearchRun, SourceResult.research_run_id == ResearchRun.id).where(ResearchRun.project_id == project_id, SourceResult.candidate_id == candidate_id).limit(1))
    if not visible:
        raise HTTPException(404, "Candidate not found")
    candidate = session.get(Candidate, candidate_id)
    profiles = session.scalars(
        select(CandidateProfile)
        .join(SourceResult, CandidateProfile.source_result_id == SourceResult.id)
        .join(ResearchRun, SourceResult.research_run_id == ResearchRun.id)
        .where(CandidateProfile.candidate_id == candidate_id, ResearchRun.project_id == project_id)
    ).all()
    return CandidateDetail(id=candidate.id, full_name=candidate.full_name, primary_email=candidate.primary_email, profiles=[{"headline": p.headline, "location": p.location, "skills": p.skills, "certifications": p.certifications, "experience": p.experience, "resume_text": p.resume_text} for p in profiles])


@app.put("/projects/{project_id}/candidates/{candidate_id}/decision", response_model=DecisionOut)
def set_decision(project_id: uuid.UUID, candidate_id: uuid.UUID, body: DecisionUpdate, session: Session = Depends(get_session)):
    candidate_detail(project_id, candidate_id, session)
    decision = session.scalar(select(ShortlistDecision).where(ShortlistDecision.project_id == project_id, ShortlistDecision.candidate_id == candidate_id))
    if decision is None:
        decision = ShortlistDecision(project_id=project_id, candidate_id=candidate_id, decided_by=user(session).id)
        session.add(decision)
    decision.decision = body.decision
    decision.notes = body.notes
    decision.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(decision)
    return decision


@app.get("/projects/{project_id}/decisions", response_model=list[DecisionOut])
def list_decisions(project_id: uuid.UUID, session: Session = Depends(get_session)):
    project_or_404(session, project_id)
    return session.scalars(select(ShortlistDecision).where(ShortlistDecision.project_id == project_id)).all()


app.mount("/app", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True), name="frontend")
