"""Serveur MCP « UEFN Vibe Starter » (stdio).

Il COMPLÈTE le serveur MCP officiel d'UEFN (Verse, Scene Graph, Devices, Session) :
ici on génère les assets (Meshy / ElevenLabs / OpenAI), on les importe via le pont
Python d'UEFN, on planifie des bâtiments et on fournit les connaissances Verse/UI.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import httpx
try:
    from mcp.server.fastmcp import Context, FastMCP
except ImportError as error:  # mcp 2.x a renommé FastMCP : pas encore supporté
    raise SystemExit(
        "Ce kit nécessite mcp 1.x (mcp>=1.28,<2). Corrige avec :  pip install \"mcp>=1.28,<2\""
    ) from error

from . import __version__, kit
from .bridge_client import BridgeClient
from .building import plan_building, summarize
from .config import Settings, find_project_name, load_settings
from .errors import BridgeUnavailable, VibeError
from .importer import ImportItem, import_items
from .jobs import advance_model_job
from .library import Library
from .paths import ensure_within, safe_name
from .providers.elevenlabs import ElevenLabsClient
from .providers.meshy import MeshyClient
from .providers.openai_images import OpenAIImageClient


class Runtime:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self.settings = settings
        self._http = http
        self.generations = 0

    def charge(self, what: str) -> None:
        """Plafond de générations payantes par session : protège les crédits contre une boucle d'agent."""
        if self.generations >= self.settings.max_generations:
            raise VibeError(
                f"Plafond de {self.settings.max_generations} générations atteint ({what} refusé). "
                "Demande à l'utilisateur de confirmer, puis relance le serveur MCP "
                "(ou augmente VIBE_MAX_GENERATIONS dans VibeStarter/.env)."
            )
        self.generations += 1

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=True)
        return self._http

    @property
    def library(self) -> Library:
        return Library(self.settings.manifest_path)

    def bridge(self) -> BridgeClient:
        return BridgeClient(self.settings.bridge_url, self.settings.bridge_token, client=self.http)

    def meshy(self) -> MeshyClient:
        return MeshyClient(self.settings.require("MESHY_API_KEY"), client=self.http)

    def eleven(self) -> ElevenLabsClient:
        return ElevenLabsClient(self.settings.require("ELEVENLABS_API_KEY"), client=self.http)

    def openai(self) -> OpenAIImageClient:
        return OpenAIImageClient(
            self.settings.require("OPENAI_API_KEY"), self.settings.openai_image_model, client=self.http
        )


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime(load_settings())
    return _runtime


def set_runtime(runtime: Runtime | None) -> None:
    global _runtime
    _runtime = runtime


mcp = FastMCP(
    "uefn-vibe-starter",
    instructions=(
        "Compagnon du MCP officiel d'UEFN. Appelle d'abord `vibe_status`, puis `uefn_guide` "
        "(topic=workflow) avant de construire. Génère les assets avec meshy_*, elevenlabs_*, "
        "openai_icon ; utilise le MCP officiel `unreal-mcp` pour Verse, devices et playtest."
    ),
)


def guard(fn):
    """Masque les clés dans les messages d'erreur et normalise les exceptions."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except VibeError as error:
            raise VibeError(get_runtime().settings.redact(str(error))) from None
        except httpx.HTTPError as error:
            raise VibeError(get_runtime().settings.redact(f"Erreur réseau : {error}")) from None
        except Exception as error:  # imprévu : on garde le type, on masque les secrets
            raise VibeError(get_runtime().settings.redact(f"{type(error).__name__}: {error}")) from None

    return wrapper


def _prefixed(name: str, prefix: str) -> str:
    clean = safe_name(name)
    return clean if clean.startswith(prefix) else f"{prefix}{clean}"


def _rel(settings: Settings, path: Path) -> str:
    try:
        return str(path.relative_to(settings.project_dir))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return str(path)


async def _progress(ctx: Context | None, value: float, message: str) -> None:
    if ctx is not None:
        try:
            await ctx.report_progress(value, 100, message)
        except Exception:  # le client n'a pas forcément demandé de progression
            pass


# --------------------------------------------------------------------------- statut
@mcp.tool()
@guard
async def vibe_status() -> dict[str, Any]:
    """Diagnostic : clés présentes (jamais leur valeur), dossier projet, pont UEFN, MCP officiel, bibliothèque."""
    rt = get_runtime()
    s = rt.settings
    status: dict[str, Any] = {
        "version": __version__,
        "project_dir": str(s.project_dir) if s.project_dir else None,
        "content_root": s.content_root,
        "keys": s.key_status(),
        "openai_image_model": s.openai_image_model,
        "generations": {"used": rt.generations, "limit": s.max_generations},
    }
    try:
        status["bridge"] = {"reachable": True, "info": await rt.bridge().call("ping")}
    except BridgeUnavailable as error:
        status["bridge"] = {"reachable": False, "hint": str(error)}
    try:
        await rt.http.get(s.official_mcp_url, timeout=httpx.Timeout(3.0))
        status["official_mcp"] = {"reachable": True, "url": s.official_mcp_url}
    except httpx.HTTPError:
        status["official_mcp"] = {
            "reachable": False,
            "hint": "Active « Python Editor Scripting » + « UEFN MCP Toolsets » dans les Project Settings d'UEFN.",
        }
    if s.project_dir:
        status["library_entries"] = len(rt.library.all())
    return status


# --------------------------------------------------------------------------- Meshy
async def _run_model_job(rt: Runtime, name: str, wait_seconds: float, ctx: Context | None) -> dict[str, Any]:
    async def on_progress(value: float, message: str) -> None:
        await _progress(ctx, value, message)

    entry = await advance_model_job(
        rt.settings, rt.meshy(), rt.library, rt.bridge(), name, wait_s=wait_seconds, on_progress=on_progress
    )
    result = {"name": name, "status": entry["status"], "stage": entry.get("stage"), "progress": entry.get("progress")}
    if entry["status"] == "pending":
        result["next"] = f"Appelle meshy_check(name='{name}') pour continuer (la génération tourne chez Meshy)."
    if entry["status"] == "failed":
        result["error"] = entry.get("error")
    if entry["status"] == "done":
        result["files"] = {k: _rel(rt.settings, Path(v)) for k, v in entry.get("files", {}).items()}
        result["import"] = entry.get("import")
    return result


def _reserve_model_name(rt: Runtime, name: str) -> None:
    existing = rt.library.get(name)
    if existing and existing.get("status") != "failed":
        raise VibeError(
            f"Le nom {name!r} existe déjà (statut {existing.get('status')}). Utilise meshy_check ou un autre nom."
        )


@mcp.tool()
@guard
async def meshy_text_to_3d(
    prompt: str,
    name: str,
    textured: bool = True,
    texture_prompt: str | None = None,
    target_polycount: int = 15000,
    wait_seconds: int = 480,
    import_to_uefn: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Génère un objet 3D (FBX) depuis un texte avec Meshy puis l'importe dans UEFN.

    textured=True enchaîne preview (géométrie) + refine (textures PBR). Garde target_polycount bas
    (≈5 000–20 000) pour les performances Fortnite. Si le délai expire, utilise meshy_check(name).
    """
    rt = get_runtime()
    name = _prefixed(name, "SM_")
    _reserve_model_name(rt, name)
    rt.charge("meshy_text_to_3d")
    task_id = await rt.meshy().create_preview(prompt, target_polycount=target_polycount)
    rt.library.put(
        name,
        {
            "kind": "model", "provider": "meshy", "source": "text", "stage": "preview",
            "task_id": task_id, "textured": textured, "texture_prompt": texture_prompt,
            "prompt": prompt, "status": "pending", "progress": 0, "import_to_uefn": import_to_uefn,
        },
    )
    return await _run_model_job(rt, name, wait_seconds, ctx)


@mcp.tool()
@guard
async def meshy_image_to_3d(
    image_path: str,
    name: str,
    texture_prompt: str | None = None,
    target_polycount: int = 15000,
    wait_seconds: int = 480,
    import_to_uefn: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Génère un objet 3D depuis une image PNG/JPEG située dans VibeStarter/ (ex. une icône openai_icon)."""
    rt = get_runtime()
    name = _prefixed(name, "SM_")
    _reserve_model_name(rt, name)
    image = ensure_within(rt.settings.vibe_dir, Path(image_path) if Path(image_path).is_absolute()
                          else rt.settings.project_dir / image_path)  # type: ignore[operator]
    if not image.is_file():
        raise VibeError(f"Image introuvable : {image_path}")
    rt.charge("meshy_image_to_3d")
    task_id = await rt.meshy().create_image_to_3d(
        image, target_polycount=target_polycount, texture_prompt=texture_prompt
    )
    rt.library.put(
        name,
        {
            "kind": "model", "provider": "meshy", "source": "image", "stage": "image",
            "task_id": task_id, "textured": True, "status": "pending", "progress": 0,
            "import_to_uefn": import_to_uefn,
        },
    )
    return await _run_model_job(rt, name, wait_seconds, ctx)


@mcp.tool()
@guard
async def meshy_check(name: str, wait_seconds: int = 60, ctx: Context | None = None) -> dict[str, Any]:
    """Reprend un job Meshy en cours (ou le finalise : téléchargement + import)."""
    return await _run_model_job(get_runtime(), _prefixed(name, "SM_"), wait_seconds, ctx)


# --------------------------------------------------------------------------- ElevenLabs
async def _store_and_import(
    rt: Runtime, name: str, kind: str, folder: str, filename: str, data: bytes,
    extra: dict[str, Any], import_to_uefn: bool,
) -> dict[str, Any]:
    path = rt.settings.inbox_dir / folder / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    entry: dict[str, Any] = {"kind": kind, "status": "done", "files": {kind: str(path)}, **extra}
    result: dict[str, Any] = {"name": name, "file": _rel(rt.settings, path), "bytes": len(data)}
    if import_to_uefn:
        imported = await import_items(rt.settings, rt.bridge(), [ImportItem(path, kind, name)])
        entry["import"] = imported
        result["import"] = imported
    rt.library.put(name, entry)
    return result


@mcp.tool()
@guard
async def elevenlabs_sound_effect(
    prompt: str,
    name: str,
    duration_seconds: float | None = None,
    loop: bool = False,
    prompt_influence: float | None = None,
    import_to_uefn: bool = True,
) -> dict[str, Any]:
    """Crée un effet sonore (WAV) avec ElevenLabs (0,5–30 s) et l'importe dans UEFN."""
    rt = get_runtime()
    name = _prefixed(name, "SFX_")
    rt.charge("elevenlabs_sound_effect")
    wav = await rt.eleven().sound_effect(
        prompt, duration_seconds=duration_seconds, prompt_influence=prompt_influence, loop=loop
    )
    return await _store_and_import(
        rt, name, "audio", "Audio", f"{name}.wav", wav, {"provider": "elevenlabs", "prompt": prompt}, import_to_uefn
    )


@mcp.tool()
@guard
async def elevenlabs_speech(
    text: str, name: str, voice_id: str, import_to_uefn: bool = True
) -> dict[str, Any]:
    """Synthèse vocale (WAV) avec ElevenLabs pour des répliques de PNJ / narration, importée dans UEFN."""
    rt = get_runtime()
    name = _prefixed(name, "VO_")
    rt.charge("elevenlabs_speech")
    wav = await rt.eleven().speech(text, voice_id)
    return await _store_and_import(
        rt, name, "audio", "Audio", f"{name}.wav", wav, {"provider": "elevenlabs", "text": text}, import_to_uefn
    )


# --------------------------------------------------------------------------- OpenAI
@mcp.tool()
@guard
async def openai_icon(
    subject: str,
    name: str,
    style: str = "Stylized game UI icon, bold clean outline, vibrant colors",
    transparent: bool = True,
    quality: str = "medium",
    import_to_uefn: bool = True,
) -> dict[str, Any]:
    """Crée une icône PNG 1024×1024 (fond transparent possible) avec OpenAI et l'importe comme texture UEFN."""
    rt = get_runtime()
    name = _prefixed(name, "T_Icon_")
    prompt = (
        f"{style}. Subject: {subject}. Single centered object, clean readable silhouette, "
        "legible at 64px, no text, no watermark, no frame."
    )
    rt.charge("openai_icon")
    png = await rt.openai().generate_png(prompt, quality=quality, transparent=transparent)
    return await _store_and_import(
        rt, name, "texture", "Textures", f"{name}.png", png, {"provider": "openai", "prompt": prompt}, import_to_uefn
    )


# --------------------------------------------------------------------------- import / bibliothèque
@mcp.tool()
@guard
async def import_to_uefn(files: list[dict[str, str]]) -> dict[str, Any]:
    """Importe des fichiers déjà présents dans VibeStarter/ : [{path, kind: model|audio|texture, name}]."""
    rt = get_runtime()
    items = []
    for spec in files:
        raw = Path(spec["path"])
        path = raw if raw.is_absolute() else rt.settings.project_dir / raw  # type: ignore[operator]
        items.append(ImportItem(path, spec["kind"], safe_name(spec["name"])))
    return await import_items(rt.settings, rt.bridge(), items)


@mcp.tool()
@guard
async def library_list() -> dict[str, Any]:
    """Liste les assets générés (nom, type, statut, fichiers)."""
    return get_runtime().library.all()


@mcp.tool()
@guard
async def save_project() -> Any:
    """Sauvegarde tous les assets modifiés dans UEFN (via le pont)."""
    return await get_runtime().bridge().call("save_all")


# --------------------------------------------------------------------------- niveau & bâtiments
@mcp.tool()
@guard
async def spawn_in_level(items: list[dict[str, Any]], label_prefix: str = "Vibe") -> Any:
    """Pose des assets dans le niveau : [{asset, location:[x,y,z] cm, rotation:[pitch,yaw,roll], scale:[x,y,z]}]."""
    return await get_runtime().bridge().call("spawn_actors", {"items": items, "label_prefix": label_prefix})


@mcp.tool()
@guard
async def build_structure(
    width_cm: float,
    depth_cm: float,
    wall_asset: str,
    floor_asset: str | None = None,
    roof_asset: str | None = None,
    doorway_asset: str | None = None,
    floors: int = 1,
    module_cm: float = 400.0,
    floor_height_cm: float = 300.0,
    origin: list[float] | None = None,
    yaw_deg: float = 0.0,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Planifie (et pose si dry_run=False) un bâtiment modulaire à partir d'assets de mur/sol/toit.

    Les modules de mur ont leur longueur sur l'axe X local (pivot centré) et mesurent module_cm.
    Les rôles sans asset (ex. pas de doorway_asset) sont ignorés. Coordonnées éditeur, en cm.
    """
    origin_t = tuple(origin) if origin else (0.0, 0.0, 0.0)
    if len(origin_t) != 3:
        raise VibeError("origin doit contenir 3 valeurs [x, y, z].")
    plan = plan_building(
        width_cm=width_cm, depth_cm=depth_cm, floors=floors, module_cm=module_cm,
        floor_height_cm=floor_height_cm, origin=origin_t, yaw_deg=yaw_deg,  # type: ignore[arg-type]
        floor_slab=floor_asset is not None, roof=roof_asset is not None,
        door=doorway_asset is not None,
    )
    assets = {"wall": wall_asset, "floor": floor_asset, "roof": roof_asset, "doorway": doorway_asset}
    items = [{**p, "asset": assets[p["role"]]} for p in plan if assets.get(p["role"])]
    result: dict[str, Any] = {"pieces": summarize(plan), "total": len(items), "dry_run": dry_run}
    if dry_run:
        result["sample"] = items[:5]
        result["next"] = "Relance avec dry_run=false pour poser le bâtiment dans le niveau."
        return result
    result["spawned"] = await get_runtime().bridge().call(
        "spawn_actors", {"items": items, "label_prefix": "Building"}
    )
    return result


# --------------------------------------------------------------------------- Verse & connaissances
def _verse_content_dir(settings: Settings) -> Path | None:
    if settings.project_dir is None:
        return None
    name = find_project_name(settings.project_dir)
    if name:
        candidate = settings.project_dir / "Plugins" / name / "Content"
        if candidate.is_dir():
            return candidate
    for found in settings.project_dir.rglob("*.verse"):
        if ".digest." not in found.name and "VibeStarter" not in found.parts:
            return found.parent
    return None


@mcp.tool()
@guard
async def verse_template(
    name: str | None = None, class_name: str = "vibe_device", write_to_project: bool = False
) -> dict[str, Any]:
    """Liste les templates Verse (name vide) ou en rend un. write_to_project écrit <class_name>.verse.

    Les templates sont des points de départ : compile-les avec l'outil Verse du MCP officiel
    et corrige les erreurs avant de les considérer valides.
    """
    if name is None:
        return {"templates": kit.list_templates()}
    code = kit.render_template(name, class_name)
    result: dict[str, Any] = {"template": name, "class_name": safe_name(class_name), "code": code}
    if write_to_project:
        folder = _verse_content_dir(get_runtime().settings)
        if folder is None:
            result["written"] = False
            result["hint"] = "Dossier Verse introuvable : écris `code` avec l'outil Verse du MCP officiel."
            return result
        target = folder / f"{safe_name(class_name)}.verse"
        if target.exists():
            raise VibeError(f"{target.name} existe déjà : choisis un autre class_name.")
        target.write_text(code, encoding="utf-8")
        result.update(written=True, path=str(target), next="Compile avec l'outil Verse du MCP officiel.")
    return result


@mcp.tool()
@guard
async def uefn_guide(topic: str | None = None) -> dict[str, Any]:
    """Guides de connaissances (workflow, verse_ui, umg_verse_fields, assets, building). Sans topic : la liste."""
    if topic is None:
        return {"topics": kit.list_guides()}
    return {"topic": topic, "content": kit.read_guide(topic)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
