"""Installe Vibe Starter dans un projet UEFN : dossier VibeStarter/, pont, jeton, .mcp.json, AGENTS.md."""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from importlib import resources
from pathlib import Path

from . import kit
from .errors import VibeError

ENV_TEMPLATE = """# Clés API de Vibe Starter. Ce fichier est ignoré par git. NE PAS le partager.
MESHY_API_KEY=
ELEVENLABS_API_KEY=
OPENAI_API_KEY=
# OPENAI_IMAGE_MODEL=gpt-image-1
# Plafond de générations payantes par session (protège tes crédits) :
# VIBE_MAX_GENERATIONS=50
"""
GITIGNORE = ".env\n.vibe_token\nInbox/\nlibrary.json\n"


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise VibeError(f"{path} n'est pas un JSON valide ({error}). Corrige-le puis relance.") from None


def install(project: Path, *, force: bool = False, python_exe: str | None = None) -> dict:
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise VibeError(f"Dossier introuvable : {project}")
    notes: list[str] = []
    if not list(project.glob("*.uefnproject")):
        notes.append("Aucun fichier .uefnproject ici : vérifie que tu pointes bien la racine du projet UEFN.")

    vibe = project / "VibeStarter"
    for sub in ("Models", "Audio", "Textures"):
        (vibe / "Inbox" / sub).mkdir(parents=True, exist_ok=True)

    bridge_src = resources.files("uefn_vibe") / "bridge" / "vibe_bridge.py"
    (vibe / "vibe_bridge.py").write_text(bridge_src.read_text(encoding="utf-8"), encoding="utf-8")

    token_file = vibe / ".vibe_token"
    if force or not token_file.is_file() or not token_file.read_text(encoding="utf-8").strip():
        token_file.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            token_file.chmod(0o600)
        except OSError:
            pass

    env_file = vibe / ".env"
    if not env_file.exists():
        env_file.write_text(ENV_TEMPLATE, encoding="utf-8")
        try:
            env_file.chmod(0o600)
        except OSError:
            pass
    (vibe / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

    mcp_path = project / ".mcp.json"
    config = _read_json(mcp_path)
    servers = config.setdefault("mcpServers", {})
    servers.setdefault("unreal-mcp", {"type": "http", "url": "http://127.0.0.1:8000/mcp"})
    if force or "uefn-vibe" not in servers:
        servers["uefn-vibe"] = {
            "command": python_exe or sys.executable,
            "args": ["-m", "uefn_vibe.server"],
            "env": {"UEFN_PROJECT_DIR": str(project)},
        }
    mcp_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    agents = project / "AGENTS.md"
    if force or not agents.exists():
        agents.write_text(kit.read_agents_md(), encoding="utf-8")
    else:
        notes.append("AGENTS.md existe déjà : conservé (utilise --force pour le remplacer).")
    claude = project / "CLAUDE.md"
    if not claude.exists():
        claude.write_text("@AGENTS.md\n", encoding="utf-8")

    return {
        "project": str(project),
        "bridge_script": str(vibe / "vibe_bridge.py"),
        "env_file": str(env_file),
        "mcp_config": str(mcp_path),
        "notes": notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="uefn-vibe-setup", description=__doc__)
    parser.add_argument("--project", required=True, type=Path, help="Racine du projet UEFN (contient le .uefnproject)")
    parser.add_argument("--python", dest="python_exe", help="Python à utiliser dans .mcp.json (défaut : celui-ci)")
    parser.add_argument("--force", action="store_true", help="Régénère le jeton, AGENTS.md et l'entrée MCP")
    args = parser.parse_args(argv)
    try:
        result = install(args.project, force=args.force, python_exe=args.python_exe)
    except VibeError as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    print(f"Vibe Starter installé dans {result['project']}\n")
    print("Étapes suivantes :")
    print(f"  1. Renseigne tes clés dans : {result['env_file']}")
    print("  2. UEFN > Project Settings : active « Python Editor Scripting » et « UEFN MCP Toolsets »")
    print(f'  3. Dans UEFN (console de sortie) : py "{result["bridge_script"]}"')
    print(f"  4. Lance ton agent (ex. claude) depuis : {result['project']}")
    for note in result["notes"]:
        print(f"  ! {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
