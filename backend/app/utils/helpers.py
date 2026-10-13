"""Shared pure utilities."""
from __future__ import annotations
import re


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()
