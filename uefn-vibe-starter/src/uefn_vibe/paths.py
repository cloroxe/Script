"""Garde-fous sur les noms et chemins manipulés par l'agent."""
from __future__ import annotations

import re
from pathlib import Path

from .errors import VibeError

_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")


def safe_name(name: str, prefix: str = "") -> str:
    """Nom d'asset UEFN valide : lettres, chiffres, underscore, ne commence pas par un chiffre."""
    cleaned = _NAME_RE.sub("_", name.strip()).strip("_")
    if not cleaned:
        raise VibeError(f"Nom d'asset invalide : {name!r}")
    cleaned = f"{prefix}{cleaned}"
    if cleaned[0].isdigit():
        cleaned = f"A_{cleaned}"
    return cleaned[:64]


def ensure_within(base: Path, candidate: Path) -> Path:
    """Résout `candidate` et refuse tout ce qui sort de `base` (.. , liens, autre disque)."""
    base_resolved = base.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise VibeError(f"Chemin refusé (hors du projet) : {candidate}") from None
    return resolved
