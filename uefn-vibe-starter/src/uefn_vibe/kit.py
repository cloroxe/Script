"""Accès aux fichiers livrés avec le paquet : templates Verse, guides, AGENTS.md."""
from __future__ import annotations

from importlib import resources

from .errors import VibeError
from .paths import safe_name

_KIT = resources.files("uefn_vibe") / "kit"


def _names(folder: str, suffix: str) -> list[str]:
    return sorted(p.name[: -len(suffix)] for p in (_KIT / folder).iterdir() if p.name.endswith(suffix))


def list_templates() -> list[str]:
    return _names("verse", ".verse")


def list_guides() -> list[str]:
    return _names("guides", ".md")


def read_template(name: str) -> str:
    if name not in list_templates():
        raise VibeError(f"Template inconnu {name!r}. Disponibles : {list_templates()}")
    return (_KIT / "verse" / f"{name}.verse").read_text(encoding="utf-8")


def render_template(name: str, class_name: str) -> str:
    return read_template(name).replace("__CLASS_NAME__", safe_name(class_name))


def read_guide(name: str) -> str:
    if name not in list_guides():
        raise VibeError(f"Guide inconnu {name!r}. Disponibles : {list_guides()}")
    return (_KIT / "guides" / f"{name}.md").read_text(encoding="utf-8")


def read_agents_md() -> str:
    return (_KIT / "AGENTS.md").read_text(encoding="utf-8")
