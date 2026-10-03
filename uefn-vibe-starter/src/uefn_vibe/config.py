"""Configuration : variables d'environnement + fichier .env du projet.

Les clés API ne sont jamais écrites dans .mcp.json ni renvoyées à l'agent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import MissingKey, VibeError

KEY_NAMES = ("MESHY_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if value:
            values[key.strip()] = value
    return values


def find_project_name(project_dir: Path) -> str | None:
    for candidate in sorted(project_dir.glob("*.uefnproject")):
        return candidate.stem
    return None


@dataclass(frozen=True)
class Settings:
    project_dir: Path | None = None
    content_root: str = "/MyIsland"
    meshy_api_key: str | None = field(default=None, repr=False)
    elevenlabs_api_key: str | None = field(default=None, repr=False)
    openai_api_key: str | None = field(default=None, repr=False)
    openai_image_model: str = "gpt-image-1"
    bridge_url: str = "http://127.0.0.1:8765"
    bridge_token: str | None = field(default=None, repr=False)
    official_mcp_url: str = "http://127.0.0.1:8000/mcp"
    max_generations: int = 50

    # -- dossiers ---------------------------------------------------------
    @property
    def vibe_dir(self) -> Path:
        if self.project_dir is None:
            raise VibeError(
                "UEFN_PROJECT_DIR n'est pas défini : lance `uefn-vibe-setup --project <dossier>` "
                "puis redémarre l'agent depuis la racine du projet."
            )
        return self.project_dir / "VibeStarter"

    @property
    def inbox_dir(self) -> Path:
        return self.vibe_dir / "Inbox"

    @property
    def manifest_path(self) -> Path:
        return self.vibe_dir / "library.json"

    # -- clés -------------------------------------------------------------
    def require(self, name: str) -> str:
        value = {
            "MESHY_API_KEY": self.meshy_api_key,
            "ELEVENLABS_API_KEY": self.elevenlabs_api_key,
            "OPENAI_API_KEY": self.openai_api_key,
        }[name]
        if not value:
            raise MissingKey(
                f"{name} est absente. Ajoute-la dans VibeStarter/.env (jamais dans le chat) "
                "puis redémarre le serveur MCP."
            )
        return value

    def key_status(self) -> dict[str, bool]:
        return {
            "MESHY_API_KEY": bool(self.meshy_api_key),
            "ELEVENLABS_API_KEY": bool(self.elevenlabs_api_key),
            "OPENAI_API_KEY": bool(self.openai_api_key),
        }

    def redact(self, text: str) -> str:
        for secret in (self.meshy_api_key, self.elevenlabs_api_key, self.openai_api_key, self.bridge_token):
            if secret:
                text = text.replace(secret, "***")
        return text


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    env = dict(os.environ if environ is None else environ)
    project_dir = Path(env["UEFN_PROJECT_DIR"]).expanduser().resolve() if env.get("UEFN_PROJECT_DIR") else None

    file_values: dict[str, str] = {}
    token: str | None = env.get("VIBE_BRIDGE_TOKEN")
    if project_dir is not None:
        file_values = parse_env_file(project_dir / "VibeStarter" / ".env")
        token_file = project_dir / "VibeStarter" / ".vibe_token"
        if not token and token_file.is_file():
            token = token_file.read_text(encoding="utf-8").strip() or None

    def pick(name: str, default: str | None = None) -> str | None:
        return env.get(name) or file_values.get(name) or default

    try:
        max_generations = max(1, int(pick("VIBE_MAX_GENERATIONS", "50") or 50))
    except ValueError:
        max_generations = 50

    project_name = find_project_name(project_dir) if project_dir else None
    content_root = pick("UEFN_CONTENT_ROOT") or (f"/{project_name}" if project_name else "/MyIsland")

    return Settings(
        project_dir=project_dir,
        content_root="/" + content_root.strip("/"),
        meshy_api_key=pick("MESHY_API_KEY"),
        elevenlabs_api_key=pick("ELEVENLABS_API_KEY"),
        openai_api_key=pick("OPENAI_API_KEY"),
        openai_image_model=pick("OPENAI_IMAGE_MODEL", "gpt-image-1") or "gpt-image-1",
        bridge_url=pick("VIBE_BRIDGE_URL", "http://127.0.0.1:8765") or "http://127.0.0.1:8765",
        bridge_token=token,
        official_mcp_url=pick("UEFN_OFFICIAL_MCP_URL", "http://127.0.0.1:8000/mcp") or "http://127.0.0.1:8000/mcp",
        max_generations=max_generations,
    )
