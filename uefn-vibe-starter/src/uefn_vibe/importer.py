"""Import des fichiers générés dans le Content Browser d'UEFN (via le pont)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bridge_client import BridgeClient
from .config import Settings
from .errors import BridgeUnavailable, VibeError
from .paths import ensure_within, safe_name

KIND_FOLDERS = {"model": "Models", "audio": "Audio", "texture": "Textures"}
KIND_EXTENSIONS = {
    "model": {".fbx"},
    "audio": {".wav", ".aif", ".flac", ".ogg"},
    "texture": {".png", ".jpg", ".jpeg", ".tga"},
}


@dataclass(frozen=True)
class ImportItem:
    path: Path
    kind: str
    name: str


def content_destination(settings: Settings, kind: str) -> str:
    return f"{settings.content_root}/VibeStarter/{KIND_FOLDERS[kind]}"


def validate_item(settings: Settings, item: ImportItem) -> ImportItem:
    if item.kind not in KIND_FOLDERS:
        raise VibeError(f"kind inconnu {item.kind!r} (attendu : {sorted(KIND_FOLDERS)})")
    resolved = ensure_within(settings.vibe_dir, item.path)
    if not resolved.is_file():
        raise VibeError(f"Fichier introuvable : {item.path}")
    if resolved.suffix.lower() not in KIND_EXTENSIONS[item.kind]:
        raise VibeError(
            f"Extension {resolved.suffix!r} non importable comme {item.kind} "
            f"(attendu : {sorted(KIND_EXTENSIONS[item.kind])})"
        )
    return ImportItem(resolved, item.kind, safe_name(item.name))


async def import_items(settings: Settings, bridge: BridgeClient, items: list[ImportItem]) -> dict:
    checked = [validate_item(settings, item) for item in items]
    payload = [
        {
            "file": str(item.path),
            "dest_path": content_destination(settings, item.kind),
            "name": item.name,
            "kind": item.kind,
        }
        for item in checked
    ]
    try:
        result = await bridge.call("import_assets", {"items": payload})
    except BridgeUnavailable as error:
        return {
            "imported": False,
            "reason": str(error),
            "manual_import": [
                {"file": str(i.path), "drag_into": content_destination(settings, i.kind), "name": i.name}
                for i in checked
            ],
        }
    return {"imported": True, "assets": result}
