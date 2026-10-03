"""Pont Python à exécuter DANS UEFN (Python Editor Scripting activé).

Il écoute sur 127.0.0.1 et exécute, sur le thread principal de l'éditeur, les commandes
envoyées par le serveur MCP `uefn-vibe-starter` : import d'assets, pose d'acteurs, sauvegarde.

Sécurité : jeton obligatoire (VibeStarter/.vibe_token), vérification du Host, JSON uniquement,
imports limités aux fichiers situés dans le dossier VibeStarter/, chemins Unreal validés.

Lancement (dans UEFN) : console de sortie -> py "<projet>\\VibeStarter\\vibe_bridge.py"
ou menu Tools -> Execute Python Script.
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:  # absent hors d'UEFN (tests)
    import unreal  # type: ignore
except ImportError:  # pragma: no cover
    unreal = None

VERSION = "0.1.0"
HOST = "127.0.0.1"
PORT = int(os.environ.get("VIBE_BRIDGE_PORT", "8765"))
try:
    ROOT = os.path.dirname(os.path.realpath(__file__))  # <projet>/VibeStarter
except NameError:  # exécuté via exec() sans __file__
    ROOT = os.path.realpath(os.environ.get("VIBE_ROOT", "."))
TOKEN_FILE = os.path.join(ROOT, ".vibe_token")
MAX_BODY = 2_000_000
MAX_SPAWN = 2000
MAIN_THREAD_TIMEOUT = 120.0

_DEST_RE = re.compile(r"^/[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_ASSET_RE = re.compile(r"^/[A-Za-z0-9_]+(/[A-Za-z0-9_]+)*(\.[A-Za-z0-9_]+)?$")
_EXTENSIONS = {
    "model": {".fbx"},
    "audio": {".wav", ".aif", ".flac", ".ogg"},
    "texture": {".png", ".jpg", ".jpeg", ".tga"},
}


def _log(message: str) -> None:
    if unreal is not None:
        unreal.log(f"[VibeBridge] {message}")
    else:  # pragma: no cover
        print(f"[VibeBridge] {message}")


class BridgeError(Exception):
    pass


# --------------------------------------------------------------------------- commandes
def _inside_root(path: str) -> bool:
    real = os.path.normcase(os.path.realpath(path))
    root = os.path.normcase(ROOT)
    return real == root or real.startswith(root + os.sep)


def _fbx_options():
    try:
        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_textures", True)
        options.set_editor_property("import_materials", True)
        options.set_editor_property("import_as_skeletal", False)
        options.static_mesh_import_data.set_editor_property("combine_meshes", True)
        return options
    except Exception as error:  # l'API peut différer selon la version d'UEFN
        _log(f"Options FBX par défaut utilisées ({error})")
        return None


def cmd_ping(_payload):
    info = {"bridge": "vibe_bridge", "version": VERSION, "root": ROOT}
    try:
        info["project_dir"] = str(unreal.Paths.project_dir())
    except Exception:
        pass
    return info


def cmd_import_assets(payload):
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise BridgeError("items doit être une liste non vide.")
    tasks, meta = [], []
    for item in items:
        kind, name, dest = item.get("kind"), item.get("name", ""), item.get("dest_path", "")
        if kind not in _EXTENSIONS:
            raise BridgeError(f"kind invalide : {kind!r}")
        if not _NAME_RE.match(name) or not _DEST_RE.match(dest):
            raise BridgeError(f"nom ou destination invalide : {name!r} / {dest!r}")
        filename = os.path.realpath(str(item.get("file", "")))
        if not _inside_root(filename) or not os.path.isfile(filename):
            raise BridgeError(f"fichier refusé (hors VibeStarter ou absent) : {item.get('file')!r}")
        if os.path.splitext(filename)[1].lower() not in _EXTENSIONS[kind]:
            raise BridgeError(f"extension non autorisée pour {kind} : {filename}")

        task = unreal.AssetImportTask()
        task.set_editor_property("automated", True)
        task.set_editor_property("filename", filename)
        task.set_editor_property("destination_path", dest)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", True)
        task.set_editor_property("save", True)
        if kind == "model":
            options = _fbx_options()
            if options is not None:
                task.set_editor_property("options", options)
        tasks.append(task)
        meta.append((name, dest, kind))

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    results = []
    for task, (name, dest, kind) in zip(tasks, meta):
        paths = [str(p) for p in task.get_editor_property("imported_object_paths")]
        results.append({"name": name, "kind": kind, "dest_path": dest, "object_paths": paths, "ok": bool(paths)})
    return results


def _vector3(value, default):
    value = value if value is not None else default
    if not (isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value)):
        raise BridgeError(f"vecteur à 3 nombres attendu, reçu {value!r}")
    return [float(v) for v in value]


def cmd_spawn_actors(payload):
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise BridgeError("items doit être une liste non vide.")
    if len(items) > MAX_SPAWN:
        raise BridgeError(f"Trop d'acteurs ({len(items)} > {MAX_SPAWN}).")
    prefix = re.sub(r"[^A-Za-z0-9_]", "_", str(payload.get("label_prefix", "Vibe")))[:32] or "Vibe"
    for item in items:
        if not _ASSET_RE.match(str(item.get("asset", ""))):
            raise BridgeError(f"chemin d'asset invalide : {item.get('asset')!r}")

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    cache, spawned, failed = {}, [], []
    for index, item in enumerate(items):
        path = item["asset"]
        if path not in cache:
            cache[path] = unreal.EditorAssetLibrary.load_asset(path)
        asset = cache[path]
        if asset is None:
            failed.append({"index": index, "asset": path, "error": "asset introuvable"})
            continue
        x, y, z = _vector3(item.get("location"), [0, 0, 0])
        pitch, yaw, roll = _vector3(item.get("rotation"), [0, 0, 0])
        sx, sy, sz = _vector3(item.get("scale"), [1, 1, 1])
        actor = subsystem.spawn_actor_from_object(
            asset, unreal.Vector(x, y, z), unreal.Rotator(roll=roll, pitch=pitch, yaw=yaw)
        )
        if actor is None:
            failed.append({"index": index, "asset": path, "error": "spawn refusé"})
            continue
        actor.set_actor_label(f"{prefix}_{index:03d}")
        actor.set_actor_scale3d(unreal.Vector(sx, sy, sz))
        spawned.append(actor.get_actor_label())
    return {"spawned": len(spawned), "failed": failed}


def cmd_save_all(_payload):
    return {"saved": bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))}


COMMANDS = {
    "ping": cmd_ping,
    "import_assets": cmd_import_assets,
    "spawn_actors": cmd_spawn_actors,
    "save_all": cmd_save_all,
}

# --------------------------------------------------------------------------- thread principal
_JOBS: "queue.Queue[_Job]" = queue.Queue()


class _Job:
    def __init__(self, fn, payload):
        self.fn, self.payload = fn, payload
        self.done = threading.Event()
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.fn(self.payload)
        except BridgeError as error:
            self.error = str(error)
        except Exception as error:  # ne jamais tuer le tick de l'éditeur
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.done.set()


def _tick(_delta_seconds=0.0):
    while True:
        try:
            job = _JOBS.get_nowait()
        except queue.Empty:
            return
        job.run()


def _run_on_main_thread(fn, payload):
    job = _Job(fn, payload)
    _JOBS.put(job)
    if not job.done.wait(MAIN_THREAD_TIMEOUT):
        raise BridgeError("l'éditeur n'a pas répondu à temps (boîte de dialogue ouverte ?)")
    if job.error:
        raise BridgeError(job.error)
    return job.result


# --------------------------------------------------------------------------- HTTP
def _make_handler(token: str, allowed_hosts: set):
    class Handler(BaseHTTPRequestHandler):
        server_version = "VibeBridge"

        def log_message(self, format, *args):  # noqa: A002
            pass

        def _reply(self, status, body):
            data = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):  # noqa: N802
            if self.headers.get("Host", "") not in allowed_hosts:
                return self._reply(403, {"ok": False, "error": "host refusé"})
            if self.path != "/rpc":
                return self._reply(404, {"ok": False, "error": "inconnu"})
            supplied = self.headers.get("X-Vibe-Token", "")
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                return self._reply(401, {"ok": False, "error": "jeton invalide"})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._reply(415, {"ok": False, "error": "JSON attendu"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                return self._reply(413, {"ok": False, "error": "corps invalide ou trop gros"})
            try:
                request = json.loads(self.rfile.read(length))
                command = COMMANDS[request["command"]]
                payload = request.get("payload") or {}
            except (ValueError, KeyError, TypeError):
                return self._reply(400, {"ok": False, "error": "requête invalide"})
            try:
                return self._reply(200, {"ok": True, "result": _run_on_main_thread(command, payload)})
            except BridgeError as error:
                return self._reply(200, {"ok": False, "error": str(error)})

    return Handler


class _State:
    def __init__(self, server, thread, tick_handle):
        self.server, self.thread, self.tick_handle = server, thread, tick_handle

    def stop(self):
        try:
            unreal.unregister_slate_post_tick_callback(self.tick_handle)
        except Exception:
            pass
        self.server.shutdown()
        self.server.server_close()


def start(port: int | None = None):
    """Démarre le pont (remplace une instance précédente lancée dans la même session UEFN)."""
    global PORT
    if port is not None:
        PORT = port
    previous = getattr(unreal, "_vibe_bridge_state", None)
    if previous is not None:
        previous.stop()
    if not os.path.isfile(TOKEN_FILE):
        raise BridgeError(f"Jeton absent ({TOKEN_FILE}). Lance `uefn-vibe-setup` d'abord.")
    with open(TOKEN_FILE, encoding="utf-8") as handle:
        token = handle.read().strip()
    if not token:
        raise BridgeError("Jeton vide : relance `uefn-vibe-setup --force`.")

    tick_handle = unreal.register_slate_post_tick_callback(_tick)
    allowed_hosts: set = set()
    server = ThreadingHTTPServer((HOST, PORT), _make_handler(token, allowed_hosts))
    bound_port = server.server_address[1]
    allowed_hosts.update({f"{HOST}:{bound_port}", f"localhost:{bound_port}"})
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.1), name="VibeBridge", daemon=True
    )
    thread.start()
    state = _State(server, thread, tick_handle)
    unreal._vibe_bridge_state = state
    _log(f"Pont prêt sur http://{HOST}:{bound_port}  (dossier : {ROOT})")
    return state


if __name__ == "__main__":
    start()
