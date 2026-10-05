import asyncio
from typing import Protocol

from pydantic import BaseModel, Field

from hyro.config import settings


class GitHubProfile(BaseModel):
    id: str
    login: str
    name: str
    html_url: str
    bio: str = ""
    location: str = ""
    topics: list[str] = Field(default_factory=list)
    email: str | None = None


class NaukriProfile(BaseModel):
    id: str
    name: str
    profile_url: str
    email: str | None = None
    headline: str = ""
    location: str = ""
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    years_experience: int = 0
    resume_text: str | None = None
    ats_score: float | None = None


class WebSearchResult(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    person_name: str
    skills: list[str] = Field(default_factory=list)


class Provider(Protocol):
    name: str

    async def fetch_page(self, query: str, cursor: int, page_size: int) -> tuple[list[dict], int | None]: ...


FIXTURES = {
    "github": [
        GitHubProfile(id="gh-1", login="asha-dev", name="Asha Rao", html_url="https://github.com/asha-dev", bio="Senior Python and SQL engineer", location="Bengaluru", topics=["Python", "SQL", "AWS"], email="asha@example.test").model_dump(),
        GitHubProfile(id="gh-2", login="ben-data", name="Ben Shah", html_url="https://github.com/ben-data", bio="Data engineer", location="Pune", topics=["Python", "Spark"]).model_dump(),
    ],
    "naukri": [
        NaukriProfile(id="nk-1", name="Asha Rao", profile_url="https://www.naukri.com/profile/asha", email="asha@example.test", headline="Senior backend engineer", location="Bengaluru", skills=["Python", "SQL", "AWS"], years_experience=6, resume_text="6 years Python SQL AWS backend engineering", ats_score=87).model_dump(),
        NaukriProfile(id="nk-2", name="Chitra Iyer", profile_url="https://www.naukri.com/profile/chitra", headline="Backend developer", location="Remote", skills=["Python", "PostgreSQL"], years_experience=4).model_dump(),
    ],
    "web": [
        WebSearchResult(id="web-1", title="Asha Rao - developer", url="https://github.com/asha-dev", snippet="Python SQL AWS engineer", person_name="Asha Rao", skills=["Python", "SQL", "AWS"]).model_dump(),
        WebSearchResult(id="web-2", title="Dev Kumar - developer", url="https://example.test/dev-kumar", snippet="Java developer", person_name="Dev Kumar", skills=["Java"]).model_dump(),
    ],
}


class MockProvider:
    def __init__(self, name: str):
        self.name = name
        self.failed_cursors: set[int] = set()

    async def fetch_page(self, query: str, cursor: int, page_size: int) -> tuple[list[dict], int | None]:
        await asyncio.sleep(settings.mock_page_delay_seconds)
        if settings.mock_fail_once_source == self.name and cursor == settings.mock_fail_once_cursor and cursor not in self.failed_cursors:
            self.failed_cursors.add(cursor)
            raise ConnectionError(f"Simulated transient {self.name} provider failure at cursor {cursor}")
        rows = FIXTURES[self.name]
        page = rows[cursor:cursor + page_size]
        next_cursor = cursor + page_size if cursor + page_size < len(rows) else None
        return page, next_cursor


PROVIDERS: dict[str, Provider] = {name: MockProvider(name) for name in FIXTURES}


def normalize(source: str, raw: dict) -> dict:
    if source == "github":
        p = GitHubProfile.model_validate(raw)
        return {"external_id": p.id, "name": p.name, "email": p.email, "url": p.html_url, "headline": p.bio, "location": p.location, "skills": p.topics, "certifications": [], "years": None, "resume_text": None, "ats_score": None}
    if source == "naukri":
        p = NaukriProfile.model_validate(raw)
        return {"external_id": p.id, "name": p.name, "email": p.email, "url": p.profile_url, "headline": p.headline, "location": p.location, "skills": p.skills, "certifications": p.certifications, "years": p.years_experience, "resume_text": p.resume_text, "ats_score": p.ats_score}
    p = WebSearchResult.model_validate(raw)
    return {"external_id": p.id, "name": p.person_name, "email": None, "url": p.url, "headline": p.snippet, "location": None, "skills": p.skills, "certifications": [], "years": None, "resume_text": None, "ats_score": None}
