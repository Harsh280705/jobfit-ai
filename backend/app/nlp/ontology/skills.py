"""Canonical skill ontology: aliases + relationships + categories."""
from __future__ import annotations
import json
import os

ALIASES: dict[str, str] = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "k8s": "Kubernetes",
    "js": "JavaScript",
    "ts": "TypeScript",
    "tf": "TensorFlow",
    "tensor flow": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "amazon web services": "AWS",
    "aws": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "azure": "Azure",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "reactjs": "React",
    "react.js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "fast api": "FastAPI",
    "fastapi": "FastAPI",
    "ci/cd": "CI/CD",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "sql": "SQL",
    "python": "Python",
    "java": "Java",
    "c++": "C++",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "terraform": "Terraform",
    "jenkins": "Jenkins",
    "airflow": "Airflow",
    "spark": "Spark",
    "hadoop": "Hadoop",
    "pandas": "pandas",
    "numpy": "NumPy",
    "django": "Django",
    "flask": "Flask",
    "spring": "Spring",
    "angular": "Angular",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "kafka": "Kafka",
    "graphql": "GraphQL",
    "rest": "REST",
    "linux": "Linux",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
}

CANONICAL: dict[str, str] = {
    "Python": "PROGRAMMING_LANGUAGE",
    "Java": "PROGRAMMING_LANGUAGE",
    "JavaScript": "PROGRAMMING_LANGUAGE",
    "TypeScript": "PROGRAMMING_LANGUAGE",
    "C++": "PROGRAMMING_LANGUAGE",
    "Go": "PROGRAMMING_LANGUAGE",
    "Rust": "PROGRAMMING_LANGUAGE",
    "SQL": "DATABASE",
    "PostgreSQL": "DATABASE",
    "MongoDB": "DATABASE",
    "Redis": "DATABASE",
    "MySQL": "DATABASE",
    "React": "FRAMEWORK",
    "Angular": "FRAMEWORK",
    "Vue.js": "FRAMEWORK",
    "Django": "FRAMEWORK",
    "Flask": "FRAMEWORK",
    "FastAPI": "FRAMEWORK",
    "Spring": "FRAMEWORK",
    "Node.js": "FRAMEWORK",
    "PyTorch": "FRAMEWORK",
    "TensorFlow": "FRAMEWORK",
    "scikit-learn": "FRAMEWORK",
    "pandas": "TOOL",
    "NumPy": "TOOL",
    "Spark": "TOOL",
    "Hadoop": "TOOL",
    "Airflow": "TOOL",
    "Kafka": "TOOL",
    "Docker": "TOOL",
    "Kubernetes": "CLOUD",
    "AWS": "CLOUD",
    "GCP": "CLOUD",
    "Azure": "CLOUD",
    "Terraform": "CLOUD",
    "Jenkins": "TOOL",
    "Git": "TOOL",
    "GitHub": "TOOL",
    "GitLab": "TOOL",
    "Linux": "TOOL",
    "GraphQL": "TOOL",
    "REST": "TOOL",
    "CI/CD": "TOOL",
    "Machine Learning": "DOMAIN",
    "Deep Learning": "DOMAIN",
    "NLP": "DOMAIN",
}

# (skill_a, skill_b, relation_type, strength 0..1)
RELATIONSHIPS: list[tuple[str, str, str, float]] = [
    ("PyTorch", "TensorFlow", "TRANSFERABLE", 0.85),
    ("TensorFlow", "PyTorch", "TRANSFERABLE", 0.85),
    ("PyTorch", "JAX", "TRANSFERABLE", 0.6),
    ("scikit-learn", "Machine Learning", "SUBSET", 0.7),
    ("PyTorch", "Deep Learning", "SUBSET", 0.7),
    ("TensorFlow", "Deep Learning", "SUBSET", 0.7),
    ("React", "Angular", "TRANSFERABLE", 0.6),
    ("React", "Vue.js", "TRANSFERABLE", 0.65),
    ("Angular", "Vue.js", "TRANSFERABLE", 0.6),
    ("Django", "Flask", "TRANSFERABLE", 0.7),
    ("Django", "FastAPI", "TRANSFERABLE", 0.65),
    ("Flask", "FastAPI", "TRANSFERABLE", 0.7),
    ("PostgreSQL", "MySQL", "TRANSFERABLE", 0.75),
    ("PostgreSQL", "SQL", "SUBSET", 0.9),
    ("MySQL", "SQL", "SUBSET", 0.9),
    ("MongoDB", "PostgreSQL", "RELATED", 0.4),
    ("Docker", "Kubernetes", "DEPENDENCY", 0.6),
    ("AWS", "GCP", "TRANSFERABLE", 0.7),
    ("AWS", "Azure", "TRANSFERABLE", 0.7),
    ("GCP", "Azure", "TRANSFERABLE", 0.7),
    ("Java", "Python", "RELATED", 0.35),
    ("JavaScript", "TypeScript", "SUPERSET", 0.85),
    ("Machine Learning", "Deep Learning", "SUPERSET", 0.6),
    ("NLP", "Machine Learning", "SUBSET", 0.7),
]


def normalize_skill(raw: str) -> str:
    key = (raw or "").strip().lower()
    if key in ALIASES:
        return ALIASES[key]
    # title-case fallback preserving known canonical casing
    for canon in CANONICAL:
        if canon.lower() == key:
            return canon
    return (raw or "").strip()


def skill_category(skill: str) -> str:
    return CANONICAL.get(skill, "OTHER")


def transfer_strength(required: str, candidate_skill: str) -> tuple[str | None, float]:
    """Return (relation_type, strength) if a configured relation exists."""
    r, c = normalize_skill(required), normalize_skill(candidate_skill)
    if r == c:
        return ("ALIAS", 1.0)
    for a, b, rel, strength in RELATIONSHIPS:
        if a == r and b == c:
            return (rel, strength)
    return (None, 0.0)


def known_skills() -> list[str]:
    return sorted(set(list(CANONICAL.keys())))
