import re

from hyro.schemas import Requirements

KNOWN_SKILLS = ["Python", "SQL", "AWS", "Java", "React", "Go", "Spark", "PostgreSQL", "Docker"]


def extract_requirements(text: str) -> Requirements:
    skills = [skill for skill in KNOWN_SKILLS if re.search(r"\b" + re.escape(skill) + r"\b", text, re.I)]
    years = re.search(r"(\d+)\s*\+?\s*years?", text, re.I)
    return Requirements(required_skills=skills, minimum_years_experience=int(years.group(1)) if years else None)


def score(requirements: Requirements, profiles: list[dict]) -> dict:
    skills = {s.lower() for p in profiles for s in p["skills"]}
    required = requirements.required_skills
    preferred = requirements.preferred_skills
    matched = [s for s in required if s.lower() in skills]
    missing = [s for s in required if s.lower() not in skills]
    required_score = 100 * len(matched) / len(required) if required else 100
    preferred_score = 100 * sum(s.lower() in skills for s in preferred) / len(preferred) if preferred else 100
    years = max((p.get("years") or 0 for p in profiles), default=0)
    exp_score = min(100, 100 * years / requirements.minimum_years_experience) if requirements.minimum_years_experience else 100
    text = " ".join((p.get("headline") or "") + " " + (p.get("resume_text") or "") for p in profiles).lower()
    semantic_terms = list(dict.fromkeys(required + preferred))
    semantic_score = 100 * sum(term.lower() in text for term in semantic_terms) / len(semantic_terms) if semantic_terms else 100
    weights = {"required_skills": .4, "experience": .25, "preferred_skills": .15, "semantic_fit": .2}
    values = {"required_skills": required_score, "experience": exp_score, "preferred_skills": preferred_score, "semantic_fit": semantic_score}
    total = round(sum(values[k] * weights[k] for k in weights), 2)
    evidence = sum(bool(p.get("resume_text")) + bool(p.get("years")) + bool(p.get("skills")) for p in profiles)
    confidence = round(min(.95, .35 + .12 * evidence), 3)
    if requirements.minimum_years_experience and years < requirements.minimum_years_experience:
        missing.append(f"{requirements.minimum_years_experience} years experience (observed {years})")
    return {"match_score": total, "confidence": confidence, "score_breakdown": {k: {"score": round(values[k], 2), "weight": weights[k]} for k in weights}, "matched_requirements": matched, "missing_requirements": missing, "reasoning": f"Matched {len(matched)}/{len(required)} required skills; highest verified experience: {years} years.", "scoring_version": "deterministic-v1"}
