"""
Skill Taxonomy & Ontology
Maps raw skill strings to normalized categories with semantic groupings.
This prevents "Python" and "python3" from being treated as different skills,
and understands that "React" implies "JavaScript".
"""

from typing import Dict, List, Set, Optional
import re

# ─── Skill Normalization Map ──────────────────────────────────────────────────
# Maps aliases → canonical name
SKILL_ALIASES: Dict[str, str] = {
    # Python ecosystem
    "python3": "python", "py": "python", "python 3": "python",
    "pytorch": "pytorch", "torch": "pytorch",
    "tensorflow": "tensorflow", "tf": "tensorflow",
    "scikit-learn": "scikit-learn", "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "huggingface": "hugging face transformers", "hf transformers": "hugging face transformers",
    "langchain": "langchain", "lang chain": "langchain",

    # JavaScript ecosystem
    "js": "javascript", "es6": "javascript", "es2015": "javascript",
    "node": "node.js", "nodejs": "node.js", "node js": "node.js",
    "react": "react.js", "reactjs": "react.js", "react js": "react.js",
    "vue": "vue.js", "vuejs": "vue.js",
    "angular": "angular", "angularjs": "angular",
    "next": "next.js", "nextjs": "next.js",
    "ts": "typescript",

    # Cloud
    "aws": "amazon web services", "amazon aws": "amazon web services",
    "gcp": "google cloud platform", "google cloud": "google cloud platform",
    "azure": "microsoft azure", "ms azure": "microsoft azure",

    # Databases
    "postgres": "postgresql", "psql": "postgresql",
    "mongo": "mongodb", "mongo db": "mongodb",
    "mysql": "mysql", "my sql": "mysql",
    "redis": "redis", "elasticache": "redis",
    "elastic": "elasticsearch", "elastic search": "elasticsearch",

    # DevOps
    "k8s": "kubernetes", "kube": "kubernetes",
    "docker": "docker", "dockerfile": "docker",
    "ci/cd": "ci/cd", "cicd": "ci/cd",
    "github actions": "github actions", "gh actions": "github actions",

    # Data
    "spark": "apache spark", "pyspark": "apache spark",
    "kafka": "apache kafka",
    "airflow": "apache airflow",
    "dbt": "dbt",
    "tableau": "tableau",
    "power bi": "power bi", "powerbi": "power bi",

    # ML/AI
    "nlp": "natural language processing",
    "cv": "computer vision",
    "ml": "machine learning",
    "dl": "deep learning",
    "llm": "large language models",
    "rag": "retrieval augmented generation",
    "genai": "generative ai", "gen ai": "generative ai",
    "openai": "openai api",
    "gpt": "gpt models",
    "bert": "bert",
    "transformers": "transformer models",
    "vector db": "vector databases", "vectordb": "vector databases",
    "faiss": "faiss",
    "pinecone": "pinecone",
    "weaviate": "weaviate",
    "chroma": "chromadb",

    # Languages
    "c++": "c++", "cpp": "c++",
    "c#": "c#", "csharp": "c#",
    "golang": "go", "go lang": "go",
    "rust": "rust",
    "java": "java",
    "scala": "scala",
    "r": "r programming",
    "matlab": "matlab",
    "sql": "sql",
    "nosql": "nosql",

    # Soft skills
    "communication": "communication",
    "leadership": "leadership",
    "problem solving": "problem solving",
    "teamwork": "teamwork",
    "agile": "agile", "scrum": "scrum",
}

# ─── Skill Categories ─────────────────────────────────────────────────────────
SKILL_CATEGORIES: Dict[str, List[str]] = {
    "programming_languages": [
        "python", "javascript", "typescript", "java", "c++", "c#", "go",
        "rust", "scala", "r programming", "matlab", "sql", "kotlin", "swift",
        "php", "ruby", "bash", "shell scripting"
    ],
    "ml_ai_core": [
        "machine learning", "deep learning", "natural language processing",
        "computer vision", "reinforcement learning", "large language models",
        "generative ai", "retrieval augmented generation", "transformer models",
        "bert", "gpt models", "fine-tuning", "prompt engineering"
    ],
    "ml_frameworks": [
        "pytorch", "tensorflow", "scikit-learn", "keras", "jax",
        "hugging face transformers", "langchain", "llamaindex", "openai api",
        "anthropic api", "groq api"
    ],
    "data_engineering": [
        "apache spark", "apache kafka", "apache airflow", "dbt",
        "apache hadoop", "flink", "databricks", "snowflake", "bigquery",
        "redshift", "etl", "data pipelines", "data warehousing"
    ],
    "databases": [
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "cassandra", "dynamodb", "sqlite", "oracle", "nosql",
        "vector databases", "faiss", "pinecone", "weaviate", "chromadb"
    ],
    "cloud_devops": [
        "amazon web services", "google cloud platform", "microsoft azure",
        "docker", "kubernetes", "terraform", "ci/cd", "github actions",
        "jenkins", "ansible", "helm", "istio", "prometheus", "grafana"
    ],
    "web_frontend": [
        "react.js", "vue.js", "angular", "next.js", "html", "css",
        "tailwind css", "webpack", "vite", "graphql", "rest api"
    ],
    "web_backend": [
        "node.js", "fastapi", "django", "flask", "spring boot",
        "express.js", "microservices", "grpc", "rabbitmq"
    ],
    "data_visualization": [
        "tableau", "power bi", "matplotlib", "seaborn", "plotly",
        "d3.js", "looker"
    ],
    "soft_skills": [
        "communication", "leadership", "problem solving", "teamwork",
        "agile", "scrum", "project management", "mentoring", "stakeholder management"
    ],
}

# Reverse map: skill → category
SKILL_TO_CATEGORY: Dict[str, str] = {}
for cat, skills in SKILL_CATEGORIES.items():
    for skill in skills:
        SKILL_TO_CATEGORY[skill] = cat

# ─── Skill Implication Graph ──────────────────────────────────────────────────
# If you know X, you likely also know Y (implied skills)
SKILL_IMPLICATIONS: Dict[str, List[str]] = {
    "react.js": ["javascript", "html", "css"],
    "next.js": ["react.js", "javascript", "node.js"],
    "pytorch": ["python", "deep learning"],
    "tensorflow": ["python", "deep learning"],
    "scikit-learn": ["python", "machine learning"],
    "apache spark": ["python", "sql", "data engineering"],
    "kubernetes": ["docker", "devops"],
    "langchain": ["python", "large language models"],
    "fastapi": ["python", "rest api"],
    "django": ["python", "rest api"],
    "spring boot": ["java", "rest api"],
}

# ─── Seniority Level Mapping ──────────────────────────────────────────────────
SENIORITY_LEVELS = {
    "intern": 0,
    "junior": 1,
    "associate": 1,
    "mid": 2,
    "mid-level": 2,
    "senior": 3,
    "staff": 4,
    "principal": 5,
    "lead": 4,
    "tech lead": 4,
    "manager": 4,
    "director": 5,
    "vp": 6,
    "cto": 7,
    "head of": 5,
}

YEARS_TO_SENIORITY = {
    (0, 1): 0,   # intern
    (1, 3): 1,   # junior
    (3, 6): 2,   # mid
    (6, 10): 3,  # senior
    (10, 15): 4, # staff/lead
    (15, 99): 5, # principal/director
}


def normalize_skill(skill: str) -> str:
    """Normalize a raw skill string to its canonical form."""
    skill = skill.lower().strip()
    skill = re.sub(r'\s+', ' ', skill)
    return SKILL_ALIASES.get(skill, skill)


def get_skill_category(skill: str) -> Optional[str]:
    """Get the category of a normalized skill."""
    normalized = normalize_skill(skill)
    return SKILL_TO_CATEGORY.get(normalized)


def expand_skills_with_implications(skills: Set[str]) -> Set[str]:
    """Add implied skills to a skill set."""
    expanded = set(skills)
    for skill in list(skills):
        implied = SKILL_IMPLICATIONS.get(skill, [])
        expanded.update(implied)
    return expanded


def normalize_skill_list(raw_skills: List[str]) -> List[str]:
    """Normalize a list of raw skill strings."""
    seen = set()
    result = []
    for skill in raw_skills:
        normalized = normalize_skill(skill)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def compute_skill_overlap(
    candidate_skills: List[str],
    required_skills: List[str],
    nice_to_have: List[str] = None
) -> Dict[str, float]:
    """
    Compute skill overlap scores between candidate and JD.
    Returns dict with 'required_coverage', 'nice_coverage', 'total_score'.
    """
    nice_to_have = nice_to_have or []

    cand_set = set(normalize_skill_list(candidate_skills))
    cand_expanded = expand_skills_with_implications(cand_set)

    req_set = set(normalize_skill_list(required_skills))
    nice_set = set(normalize_skill_list(nice_to_have))

    if not req_set:
        required_coverage = 1.0
    else:
        matched_required = cand_expanded & req_set
        required_coverage = len(matched_required) / len(req_set)

    if not nice_set:
        nice_coverage = 0.0
    else:
        matched_nice = cand_expanded & nice_set
        nice_coverage = len(matched_nice) / len(nice_set)

    # Weighted: required matters more
    total_score = 0.75 * required_coverage + 0.25 * nice_coverage

    return {
        "required_coverage": required_coverage,
        "nice_coverage": nice_coverage,
        "total_score": total_score,
        "matched_required": list(cand_expanded & req_set),
        "missing_required": list(req_set - cand_expanded),
        "matched_nice": list(cand_expanded & nice_set),
    }


def years_to_seniority_level(years: float) -> int:
    """Convert years of experience to seniority level (0-5)."""
    for (low, high), level in YEARS_TO_SENIORITY.items():
        if low <= years < high:
            return level
    return 5
