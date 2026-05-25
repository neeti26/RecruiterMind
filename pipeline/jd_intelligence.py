"""
Stage 0 — JD Intelligence
Deeply understands a job description beyond keyword extraction.
Extracts: required skills, nice-to-have, seniority, culture signals,
implicit needs, deal-breakers, and a semantic summary for embedding.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

JD_ANALYSIS_SYSTEM_PROMPT = """You are an expert technical recruiter with 15+ years of experience.
Your job is to deeply analyze a job description and extract structured intelligence.

Go BEYOND the literal text. Infer:
- What the role ACTUALLY needs (not just what's listed)
- What kind of person thrives in this environment
- What are the real deal-breakers vs. nice-to-haves
- What seniority level is truly expected
- What domain experience is implicitly required

Respond with a JSON object following the exact schema provided."""

JD_ANALYSIS_USER_TEMPLATE = """Analyze this job description and extract structured intelligence.

JOB DESCRIPTION:
{jd_text}

Return a JSON object with this exact schema:
{{
  "role_title": "normalized job title",
  "seniority_level": "intern|junior|mid|senior|staff|principal|lead|manager|director",
  "seniority_years_min": 0,
  "seniority_years_max": 0,
  "required_skills": ["list of must-have technical skills, normalized"],
  "nice_to_have_skills": ["list of bonus skills"],
  "domain_keywords": ["key domain/industry terms that define this role"],
  "implicit_requirements": ["things not stated but clearly needed, e.g. 'experience with large codebases', 'startup mindset'"],
  "deal_breakers": ["absolute disqualifiers if present"],
  "culture_signals": ["work style, team culture, values signals from the JD"],
  "soft_skills_required": ["communication, leadership, etc."],
  "role_summary": "2-3 sentence plain English summary of what this role truly needs",
  "embedding_text": "A rich, detailed paragraph combining all aspects of the role for semantic search. Include skills, domain, seniority, culture, and implicit needs. This will be used to find semantically similar candidate profiles."
}}"""


@dataclass
class JDAnalysis:
    role_title: str
    seniority_level: str
    seniority_years_min: int
    seniority_years_max: int
    required_skills: List[str]
    nice_to_have_skills: List[str]
    domain_keywords: List[str]
    implicit_requirements: List[str]
    deal_breakers: List[str]
    culture_signals: List[str]
    soft_skills_required: List[str]
    role_summary: str
    embedding_text: str
    raw_jd: str = ""

    @classmethod
    def from_dict(cls, data: Dict, raw_jd: str = "") -> "JDAnalysis":
        return cls(
            role_title=data.get("role_title", "Unknown Role"),
            seniority_level=data.get("seniority_level", "mid"),
            seniority_years_min=int(data.get("seniority_years_min", 0)),
            seniority_years_max=int(data.get("seniority_years_max", 10)),
            required_skills=data.get("required_skills", []),
            nice_to_have_skills=data.get("nice_to_have_skills", []),
            domain_keywords=data.get("domain_keywords", []),
            implicit_requirements=data.get("implicit_requirements", []),
            deal_breakers=data.get("deal_breakers", []),
            culture_signals=data.get("culture_signals", []),
            soft_skills_required=data.get("soft_skills_required", []),
            role_summary=data.get("role_summary", ""),
            embedding_text=data.get("embedding_text", ""),
            raw_jd=raw_jd,
        )

    def to_search_text(self) -> str:
        """Generate rich text for semantic search."""
        if self.embedding_text:
            return self.embedding_text
        # Fallback: construct from parts
        parts = [
            f"Role: {self.role_title}",
            f"Seniority: {self.seniority_level}",
            f"Required skills: {', '.join(self.required_skills)}",
            f"Nice to have: {', '.join(self.nice_to_have_skills)}",
            f"Domain: {', '.join(self.domain_keywords)}",
            f"Implicit needs: {', '.join(self.implicit_requirements)}",
            f"Culture: {', '.join(self.culture_signals)}",
        ]
        return " | ".join(parts)


class JDIntelligence:
    """
    Analyzes a job description using LLM to extract deep structured intelligence.
    Falls back to rule-based extraction if LLM is unavailable.
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def analyze(self, jd_text: str) -> JDAnalysis:
        """
        Analyze a job description.
        Returns structured JDAnalysis.
        """
        if self.llm and self.llm.is_available():
            try:
                return self._llm_analyze(jd_text)
            except Exception as e:
                logger.warning(f"LLM JD analysis failed: {e}. Using rule-based fallback.")

        return self._rule_based_analyze(jd_text)

    def _llm_analyze(self, jd_text: str) -> JDAnalysis:
        """Use LLM for deep JD analysis."""
        user_prompt = JD_ANALYSIS_USER_TEMPLATE.format(jd_text=jd_text[:4000])
        result = self.llm.complete_json(JD_ANALYSIS_SYSTEM_PROMPT, user_prompt)
        return JDAnalysis.from_dict(result, raw_jd=jd_text)

    def _rule_based_analyze(self, jd_text: str) -> JDAnalysis:
        """
        Rule-based fallback JD analysis.
        Extracts skills using keyword matching and heuristics.
        """
        import re
        from utils.skill_taxonomy import SKILL_ALIASES, SENIORITY_LEVELS

        text_lower = jd_text.lower()

        # Extract skills by scanning for known skill names
        all_known_skills = list(SKILL_ALIASES.keys()) + list(set(SKILL_ALIASES.values()))
        found_skills = []
        for skill in all_known_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                canonical = SKILL_ALIASES.get(skill, skill)
                if canonical not in found_skills:
                    found_skills.append(canonical)

        # Detect seniority — look for seniority in the title/requirements context
        seniority = "mid"
        years_min, years_max = 2, 8
        # Prioritize seniority keywords near "looking for", "require", "level"
        seniority_context = re.search(
            r'(?:looking for|seeking|require|need|level)[^.]{0,50}?(senior|staff|principal|lead|junior|mid|manager|director)',
            text_lower
        )
        if seniority_context:
            seniority = seniority_context.group(1)
        else:
            # Fall back to first occurrence in title line
            for level_kw in ["senior", "staff", "principal", "lead", "junior", "mid", "manager"]:
                if level_kw in text_lower[:200]:  # only check first 200 chars (title area)
                    seniority = level_kw
                    break

        # Extract years from patterns like "3+ years", "5-7 years"
        year_patterns = re.findall(r'(\d+)\+?\s*(?:to|-)\s*(\d+)\s*years?', text_lower)
        if year_patterns:
            years_min = int(year_patterns[0][0])
            years_max = int(year_patterns[0][1])
        else:
            single_year = re.findall(r'(\d+)\+\s*years?', text_lower)
            if single_year:
                years_min = int(single_year[0])
                years_max = years_min + 4

        # Extract role title: look for explicit label first, then use first short line
        title_match = re.search(r'(?:job title|position)[:\s]+([^\n]{3,60})', text_lower)
        if title_match:
            role_title = title_match.group(1).strip().title()
        else:
            # Use first non-empty line of the original text that looks like a title
            # (short, no sentence-ending punctuation, not a section header)
            role_title = "Software Engineer"
            for line in jd_text.split('\n'):
                line = line.strip()
                if (5 < len(line) < 80
                        and not line.endswith('.')
                        and not line.endswith(':')
                        and not line.lower().startswith('about')
                        and not line.lower().startswith('we ')):
                    role_title = line
                    break

        # Build embedding text
        embedding_text = (
            f"Looking for a {seniority} {role_title} with {years_min}+ years experience. "
            f"Required skills: {', '.join(found_skills[:15])}. "
            f"Full job description: {jd_text[:500]}"
        )

        return JDAnalysis(
            role_title=role_title,
            seniority_level=seniority,
            seniority_years_min=years_min,
            seniority_years_max=years_max,
            required_skills=found_skills[:20],
            nice_to_have_skills=[],
            domain_keywords=found_skills[:5],
            implicit_requirements=[],
            deal_breakers=[],
            culture_signals=[],
            soft_skills_required=[],
            role_summary=jd_text[:300],
            embedding_text=embedding_text,
            raw_jd=jd_text,
        )
