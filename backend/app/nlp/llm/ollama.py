"""Optional LLM layer (Ollama). Structured JSON validated with Pydantic; system works without it."""
from __future__ import annotations
from pydantic import BaseModel, Field


class LLMRequirementParse(BaseModel):
    requirement_type: str = "SKILL"
    canonical_skill: str = ""
    mandatory: bool = True
    minimum_years: float | None = None
    confidence: float = 0.5
    reason: str = ""


async def llm_parse_requirement(raw_text: str) -> LLMRequirementParse | None:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.OLLAMA_ENABLED:
        return None
    try:
        import httpx  # type: ignore

        prompt = (
            "Extract a job requirement as JSON with keys: requirement_type, canonical_skill, "
            f"mandatory (bool), minimum_years (number|null), confidence, reason. Requirement: {raw_text}"
        )
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{settings.OLLAMA_BASE_URL}/api/generate", json={
                "model": settings.OLLAMA_MODEL, "prompt": prompt,
                "format": "json", "stream": False})
            r.raise_for_status()
            import json as _json

            data = r.json()
            payload = _json.loads(data.get("response", "{}"))
            return LLMRequirementParse(**payload)
    except Exception:
        return None
