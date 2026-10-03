"""Machine d'état des modèles 3D Meshy : preview -> refine (texture) -> FBX -> import."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from .bridge_client import BridgeClient
from .config import Settings
from .errors import ProviderError
from .importer import ImportItem, import_items
from .library import Library
from .providers.meshy import MeshyClient

ProgressFn = Callable[[float, str], Awaitable[None]]
TEXTURE_MAPS = ("base_color", "normal", "metallic", "roughness", "emission")


async def advance_model_job(
    settings: Settings,
    meshy: MeshyClient,
    library: Library,
    bridge: BridgeClient,
    name: str,
    *,
    wait_s: float,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Fait avancer le job `name` aussi loin que possible dans le délai `wait_s`."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait_s

    while True:
        entry = library.get(name)
        if entry is None:
            raise ProviderError(f"Aucun job nommé {name!r} dans la bibliothèque.")
        if entry["status"] in ("done", "failed"):
            return entry

        task_kind = "text-to-3d" if entry["source"] == "text" else "image-to-3d"

        async def report(progress: int, _entry=entry) -> None:
            if on_progress:
                stage_offset = 50 if _entry["stage"] == "refine" else 0
                scale = 0.5 if _entry["source"] == "text" and _entry.get("textured") else 1.0
                await on_progress(stage_offset + progress * scale, f"Meshy {_entry['stage']} {progress}%")

        remaining = max(0.0, deadline - loop.time())
        task = await meshy.wait(task_kind, entry["task_id"], timeout_s=remaining, on_progress=report)
        status = task.get("status")

        if status in ("FAILED", "CANCELED"):
            message = (task.get("task_error") or {}).get("message") or status
            return library.update(name, status="failed", error=message)
        if status != "SUCCEEDED":
            return library.update(name, status="pending", progress=task.get("progress", 0))

        if entry["source"] == "text" and entry["stage"] == "preview" and entry.get("textured"):
            refine_id = await meshy.create_refine(
                entry["task_id"], texture_prompt=entry.get("texture_prompt")
            )
            library.update(
                name, stage="refine", preview_task_id=entry["task_id"], task_id=refine_id, progress=0
            )
            continue  # on enchaîne sur la phase de texture dans le délai restant

        return await _finalize(settings, meshy, library, bridge, name, entry, task)


async def _finalize(
    settings: Settings,
    meshy: MeshyClient,
    library: Library,
    bridge: BridgeClient,
    name: str,
    entry: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
    fbx_url = (task.get("model_urls") or {}).get("fbx")
    if not fbx_url:
        return library.update(name, status="failed", error="Meshy n'a pas fourni de FBX.")

    fbx_path = await meshy.download(fbx_url, settings.inbox_dir / "Models" / f"{name}.fbx")
    files = {"model": str(fbx_path)}
    items = [ImportItem(fbx_path, "model", name)]

    maps = (task.get("texture_urls") or [{}])[0]
    for map_name in TEXTURE_MAPS:
        url = maps.get(map_name)
        if not url:
            continue
        suffix = ".png"
        path = await meshy.download(url, settings.inbox_dir / "Textures" / f"{name}_{map_name}{suffix}")
        files[map_name] = str(path)
        items.append(ImportItem(path, "texture", f"{name}_{map_name}"))

    update: dict[str, Any] = {"status": "done", "progress": 100, "files": files}
    if entry.get("import_to_uefn", True):
        update["import"] = await import_items(settings, bridge, items)
    return library.update(name, **update)
