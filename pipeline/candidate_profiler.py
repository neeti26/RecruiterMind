"""
Stage 1 — Candidate Profiler
Converts raw candidate data (CSV row / resume text) into a rich structured profile.
Handles messy real-world data gracefully.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

CANDIDATE_PROFILE_SYSTEM_PROMPT = """You are an expert recruiter parsing a candidate profile.
Extract structured information from the raw candidate data provided.
Be thorough — infer what you can from context.
Respond with valid JSON only."""

CANDIDATE_PROFILE_USER_TEMPLATE = """Parse this candidate profile into structured JSON.

CANDIDATE DATA:
{candidate_text}

Return JSON with this schema:
{{
  "name": "candidate name",
  "current_title": "current or most recent job title",
  "total_years_experience": 0.0,
  "skills": ["list of all technical and soft skills mentioned"],
  "work_history": [
    {{
      "title": "job title",
      "company": "company name",
      "start_date": "YYYY-MM or year",
      "end_date": "YYYY-MM or 'present'",
      "description": "brief role description"
    }}
  ],
  "education": [
    {{
      "degree": "degree type",
      "field": "field of study",
      "institution": "university/college name",
      "year": "graduation year"
    }}
  ],
  "certifications": ["list of certifications"],
  "github_url": "github profile url if present",
  "linkedin_url": "linkedin url if present",
  "platform_signals": {{
    "github_repos": 0,
    "github_stars": 0,
    "open_source_contributions": false,
    "blog_posts": 0,
    "kaggle_rank": "",
    "leetcode_solved": 0,
    "publications": 0
  }},
  "location": "city, country",
  "languages": ["spoken languages"],
  "summary_text": "A rich paragraph combining all candidate information for semantic matching. Include skills, experience, domain, achievements, and career trajectory."
}}"""


@dataclass
class PlatformSignals:
    github_repos: int = 0
    github_stars: int = 0
    open_source_contributions: bool = False
    blog_posts: int = 0
    kaggle_rank: str = ""
    leetcode_solved: int = 0
    publications: int = 0

    def compute_score(self) -> float:
        """Compute a 0-1 behavioral signal score from platform activity."""
        score = 0.0
        # GitHub activity
        score += min(0.25, self.github_repos * 0.01)
        score += min(0.20, self.github_stars * 0.005)
        if self.open_source_contributions:
            score += 0.20
        # Content creation
        score += min(0.10, self.blog_posts * 0.02)
        # Competitive programming
        score += min(0.10, self.leetcode_solved * 0.0005)
        # Research
        score += min(0.15, self.publications * 0.05)
        return min(1.0, score)


@dataclass
class CandidateProfile:
    candidate_id: str
    name: str
    current_title: str
    total_years_experience: float
    skills: List[str]
    work_history: List[Dict]
    education: List[Dict]
    certifications: List[str]
    platform_signals: PlatformSignals
    location: str
    languages: List[str]
    summary_text: str
    raw_data: Dict = field(default_factory=dict)

    # Computed fields (set during scoring)
    embedding: Any = field(default=None, repr=False)
    scores: Dict[str, float] = field(default_factory=dict)
    final_rank: int = 0
    final_score: float = 0.0
    confidence: float = 0.0
    explanation: str = ""
    hire_recommendation: str = ""
    key_strength: str = ""
    key_concern: str = ""
    why_hire: str = ""          # single compelling sentence for recruiters

    def to_embedding_text(self) -> str:
        """Generate rich text for semantic embedding."""
        if self.summary_text:
            return self.summary_text

        parts = [
            f"Candidate: {self.name}",
            f"Current role: {self.current_title}",
            f"Experience: {self.total_years_experience:.1f} years",
            f"Skills: {', '.join(self.skills[:30])}",
        ]
        if self.work_history:
            recent = self.work_history[:3]
            history_str = "; ".join(
                f"{j.get('title', '')} at {j.get('company', '')}"
                for j in recent
            )
            parts.append(f"Recent experience: {history_str}")
        if self.education:
            edu = self.education[0]
            parts.append(
                f"Education: {edu.get('degree', '')} in {edu.get('field', '')} "
                f"from {edu.get('institution', '')}"
            )
        if self.certifications:
            parts.append(f"Certifications: {', '.join(self.certifications[:5])}")

        return " | ".join(parts)

    def to_dict(self) -> Dict:
        """Convert to dict for output CSV."""
        gap = self.raw_data.get("_skill_gap")
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "current_title": self.current_title,
            "total_years_experience": round(self.total_years_experience, 1),
            "final_rank": self.final_rank,
            "final_score": round(self.final_score, 4),
            "confidence": round(self.confidence, 3),
            "hire_recommendation": self.hire_recommendation,
            "why_hire": self.why_hire,
            "technical_skill_match": round(self.scores.get("technical_skill_match", 0), 4),
            "career_trajectory": round(self.scores.get("career_trajectory", 0), 4),
            "domain_depth": round(self.scores.get("domain_depth", 0), 4),
            "seniority_alignment": round(self.scores.get("seniority_alignment", 0), 4),
            "behavioral_signals": round(self.scores.get("behavioral_signals", 0), 4),
            "culture_soft_fit": round(self.scores.get("culture_soft_fit", 0), 4),
            "risk_penalty": round(self.scores.get("risk_penalty", 0), 4),
            "cross_encoder_score": round(self.scores.get("cross_encoder_score", 0), 4),
            "required_skill_coverage": round(gap.required_coverage if gap else 0, 3),
            "matched_skills": ", ".join(gap.matched_required[:8]) if gap else "",
            "missing_skills": ", ".join(gap.missing_required[:5]) if gap else "",
            "critical_gaps": ", ".join(gap.critical_gaps[:3]) if gap else "",
            "key_strength": self.key_strength,
            "key_concern": self.key_concern,
            "explanation": self.explanation,
            "top_skills": ", ".join(self.skills[:10]),
            "location": self.location,
        }


class CandidateProfiler:
    """
    Converts raw candidate data into structured CandidateProfile objects.
    Handles CSV rows, JSON objects, and free-text resumes.
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def profile_from_csv_row(self, row: Dict, candidate_id: str) -> CandidateProfile:
        """
        Build a CandidateProfile from a CSV row.
        Handles various column naming conventions.
        """
        # Normalize column names
        row = {k.lower().strip().replace(" ", "_"): v for k, v in row.items()}

        name = self._get_field(row, ["name", "candidate_name", "full_name"], "Unknown")
        title = self._get_field(row, ["title", "current_title", "job_title", "position"], "")
        years = self._parse_years(self._get_field(row, [
            "years_experience", "experience", "total_experience",
            "years_of_experience", "exp", "experience_years"
        ], "0"))

        # Skills: could be comma-separated string or list
        skills_raw = self._get_field(row, ["skills", "skill_set", "technical_skills", "technologies"], "")
        skills = self._parse_skills(skills_raw)

        # Work history: could be JSON string or separate columns
        work_history = self._parse_work_history(row)

        # Education
        education = self._parse_education(row)

        # Platform signals
        platform_signals = self._parse_platform_signals(row)

        # Certifications
        certs_raw = self._get_field(row, ["certifications", "certs", "certificates"], "")
        certifications = [c.strip() for c in str(certs_raw).split(",") if c.strip()]

        location = self._get_field(row, ["location", "city", "country", "address"], "")
        languages = self._parse_list_field(row, ["languages", "spoken_languages"])

        # Build summary text for embedding
        summary = self._get_field(row, ["summary", "bio", "about", "profile_summary"], "")
        if not summary:
            summary = self._build_summary_text(
                name, title, years, skills, work_history, education
            )

        return CandidateProfile(
            candidate_id=candidate_id,
            name=name,
            current_title=title,
            total_years_experience=years,
            skills=skills,
            work_history=work_history,
            education=education,
            certifications=certifications,
            platform_signals=platform_signals,
            location=location,
            languages=languages,
            summary_text=summary,
            raw_data=dict(row),
        )

    def profile_from_text(self, text: str, candidate_id: str) -> CandidateProfile:
        """Build a CandidateProfile from free-text resume."""
        if self.llm and self.llm.is_available():
            try:
                return self._llm_profile(text, candidate_id)
            except Exception as e:
                logger.warning(f"LLM profiling failed: {e}")

        return self._rule_based_profile(text, candidate_id)

    def _llm_profile(self, text: str, candidate_id: str) -> CandidateProfile:
        """Use LLM to parse free-text resume."""
        user_prompt = CANDIDATE_PROFILE_USER_TEMPLATE.format(
            candidate_text=text[:3000]
        )
        data = self.llm.complete_json(CANDIDATE_PROFILE_SYSTEM_PROMPT, user_prompt)

        platform_data = data.get("platform_signals", {})
        platform_signals = PlatformSignals(
            github_repos=int(platform_data.get("github_repos", 0)),
            github_stars=int(platform_data.get("github_stars", 0)),
            open_source_contributions=bool(platform_data.get("open_source_contributions", False)),
            blog_posts=int(platform_data.get("blog_posts", 0)),
            kaggle_rank=str(platform_data.get("kaggle_rank", "")),
            leetcode_solved=int(platform_data.get("leetcode_solved", 0)),
            publications=int(platform_data.get("publications", 0)),
        )

        return CandidateProfile(
            candidate_id=candidate_id,
            name=data.get("name", "Unknown"),
            current_title=data.get("current_title", ""),
            total_years_experience=float(data.get("total_years_experience", 0)),
            skills=data.get("skills", []),
            work_history=data.get("work_history", []),
            education=data.get("education", []),
            certifications=data.get("certifications", []),
            platform_signals=platform_signals,
            location=data.get("location", ""),
            languages=data.get("languages", []),
            summary_text=data.get("summary_text", text[:500]),
            raw_data={"raw_text": text},
        )

    def _rule_based_profile(self, text: str, candidate_id: str) -> CandidateProfile:
        """Rule-based fallback for free-text resumes."""
        from utils.skill_taxonomy import SKILL_ALIASES

        text_lower = text.lower()

        # Extract skills
        skills = []
        for alias, canonical in SKILL_ALIASES.items():
            if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                if canonical not in skills:
                    skills.append(canonical)

        # Extract years
        year_matches = re.findall(r'(\d+)\+?\s*years?', text_lower)
        years = max([int(y) for y in year_matches], default=0)

        # Extract name (first line heuristic)
        first_line = text.strip().split('\n')[0].strip()
        name = first_line if len(first_line) < 50 else "Unknown"

        return CandidateProfile(
            candidate_id=candidate_id,
            name=name,
            current_title="",
            total_years_experience=float(years),
            skills=skills[:30],
            work_history=[],
            education=[],
            certifications=[],
            platform_signals=PlatformSignals(),
            location="",
            languages=[],
            summary_text=text[:500],
            raw_data={"raw_text": text},
        )

    # ── Helper methods ────────────────────────────────────────────────────────

    def _get_field(self, row: Dict, keys: List[str], default: str = "") -> str:
        for key in keys:
            if key in row and row[key] is not None and str(row[key]).strip():
                return str(row[key]).strip()
        return default

    def _parse_years(self, value: str) -> float:
        try:
            # Handle "5+ years", "3-5 years", "5 years"
            nums = re.findall(r'\d+\.?\d*', str(value))
            if nums:
                return float(nums[0])
        except Exception:
            pass
        return 0.0

    def _parse_skills(self, raw: str) -> List[str]:
        if not raw:
            return []
        from utils.skill_taxonomy import normalize_skill_list
        # Handle JSON array strings
        if raw.startswith('['):
            try:
                import json
                skills = json.loads(raw)
                return normalize_skill_list([str(s) for s in skills])
            except Exception:
                pass
        # Comma or pipe separated
        separators = [',', '|', ';', '\n']
        for sep in separators:
            if sep in raw:
                parts = [p.strip() for p in raw.split(sep) if p.strip()]
                return normalize_skill_list(parts)
        return normalize_skill_list([raw.strip()])

    def _parse_work_history(self, row: Dict) -> List[Dict]:
        # Try JSON field first
        for key in ["work_history", "experience", "employment_history", "jobs"]:
            if key in row and row[key]:
                try:
                    import json
                    data = json.loads(str(row[key]))
                    if isinstance(data, list):
                        return data
                except Exception:
                    pass

        # Try to construct from separate columns
        history = []
        for i in range(1, 6):  # up to 5 jobs
            title_key = f"job{i}_title" if f"job{i}_title" in row else f"title_{i}"
            company_key = f"job{i}_company" if f"job{i}_company" in row else f"company_{i}"
            if title_key in row and row[title_key]:
                history.append({
                    "title": str(row.get(title_key, "")),
                    "company": str(row.get(company_key, "")),
                    "start_date": str(row.get(f"job{i}_start", "")),
                    "end_date": str(row.get(f"job{i}_end", "present")),
                })
        return history

    def _parse_education(self, row: Dict) -> List[Dict]:
        for key in ["education", "academic_background"]:
            if key in row and row[key]:
                try:
                    import json
                    data = json.loads(str(row[key]))
                    if isinstance(data, list):
                        return data
                except Exception:
                    pass

        edu = {}
        for key in ["degree", "highest_degree", "qualification"]:
            if key in row and row[key]:
                edu["degree"] = str(row[key])
                break
        for key in ["field_of_study", "major", "specialization"]:
            if key in row and row[key]:
                edu["field"] = str(row[key])
                break
        for key in ["university", "college", "institution", "school"]:
            if key in row and row[key]:
                edu["institution"] = str(row[key])
                break
        for key in ["graduation_year", "grad_year", "year_of_graduation"]:
            if key in row and row[key]:
                edu["year"] = str(row[key])
                break

        return [edu] if edu else []

    def _parse_platform_signals(self, row: Dict) -> PlatformSignals:
        return PlatformSignals(
            github_repos=int(self._parse_years(self._get_field(
                row, ["github_repos", "github_repositories", "repos"], "0"
            ))),
            github_stars=int(self._parse_years(self._get_field(
                row, ["github_stars", "stars"], "0"
            ))),
            open_source_contributions=str(self._get_field(
                row, ["open_source", "oss_contributions", "open_source_contributions"], "false"
            )).lower() in ("true", "yes", "1"),
            blog_posts=int(self._parse_years(self._get_field(
                row, ["blog_posts", "articles", "medium_posts"], "0"
            ))),
            kaggle_rank=self._get_field(row, ["kaggle_rank", "kaggle"], ""),
            leetcode_solved=int(self._parse_years(self._get_field(
                row, ["leetcode_solved", "leetcode", "problems_solved"], "0"
            ))),
            publications=int(self._parse_years(self._get_field(
                row, ["publications", "papers", "research_papers"], "0"
            ))),
        )

    def _parse_list_field(self, row: Dict, keys: List[str]) -> List[str]:
        raw = self._get_field(row, keys, "")
        if not raw:
            return []
        return [x.strip() for x in re.split(r'[,;|]', raw) if x.strip()]

    def _build_summary_text(
        self, name: str, title: str, years: float,
        skills: List[str], work_history: List[Dict], education: List[Dict]
    ) -> str:
        parts = [f"{name} is a {title}" if title else name]
        if years > 0:
            parts.append(f"with {years:.0f} years of experience")
        if skills:
            parts.append(f"skilled in {', '.join(skills[:15])}")
        if work_history:
            recent = work_history[:2]
            companies = [j.get("company", "") for j in recent if j.get("company")]
            if companies:
                parts.append(f"previously at {', '.join(companies)}")
        if education:
            edu = education[0]
            if edu.get("degree") and edu.get("institution"):
                parts.append(
                    f"holds a {edu['degree']} from {edu['institution']}"
                )
        return ". ".join(parts) + "."
