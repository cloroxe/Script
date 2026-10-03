"""Faux module `unreal` : juste assez pour exercer la logique du pont (HTTP, jeton, chemins, file d'attente)."""
import threading
import time
import types


def build():
    m = types.ModuleType("unreal")
    m.logs = []
    m.log = m.logs.append
    m._callbacks = []
    m.imported = []
    m.spawned = []
    m.saved = []
    m.thread_names = []

    def register(fn):
        m._callbacks.append(fn)
        return len(m._callbacks) - 1

    m.register_slate_post_tick_callback = register
    m.unregister_slate_post_tick_callback = lambda handle: m._callbacks.__setitem__(handle, None)

    class _Props:
        def __init__(self):
            self.props = {}

        def set_editor_property(self, key, value):
            self.props[key] = value

        def get_editor_property(self, key):
            return self.props[key]

    class AssetImportTask(_Props):
        pass

    class FbxImportUI(_Props):
        def __init__(self):
            super().__init__()
            self.static_mesh_import_data = _Props()

    class _AssetTools:
        def import_asset_tasks(self, tasks):
            m.thread_names.append(threading.current_thread().name)
            for task in tasks:
                p = task.props
                m.imported.append(p)
                ok = "fail" not in p["destination_name"]
                task.props["imported_object_paths"] = [f"{p['destination_path']}/{p['destination_name']}"] if ok else []

    m.AssetImportTask = AssetImportTask
    m.FbxImportUI = FbxImportUI
    m.AssetToolsHelpers = types.SimpleNamespace(get_asset_tools=lambda: _AssetTools())
    m.Paths = types.SimpleNamespace(project_dir=lambda: "C:/Projects/MyIsland/")
    m.Vector = lambda x=0.0, y=0.0, z=0.0: ("vec", x, y, z)
    m.Rotator = lambda roll=0.0, pitch=0.0, yaw=0.0: ("rot", roll, pitch, yaw)

    class _Actor:
        def __init__(self, asset, loc, rot):
            self.asset, self.loc, self.rot, self.label, self.scale = asset, loc, rot, None, None

        def set_actor_label(self, label):
            self.label = label

        def get_actor_label(self):
            return self.label

        def set_actor_scale3d(self, scale):
            self.scale = scale

    class _ActorSubsystem:
        def spawn_actor_from_object(self, asset, loc, rot):
            m.thread_names.append(threading.current_thread().name)
            actor = _Actor(asset, loc, rot)
            m.spawned.append(actor)
            return actor

    m.EditorActorSubsystem = _ActorSubsystem
    m.get_editor_subsystem = lambda cls: cls()
    m.EditorAssetLibrary = types.SimpleNamespace(
        load_asset=lambda path: None if "Missing" in path else f"asset:{path}"
    )
    m.EditorLoadingAndSavingUtils = types.SimpleNamespace(
        save_dirty_packages=lambda a, b: m.saved.append((a, b)) or True
    )

    # « tick » de l'éditeur sur un thread nommé comme le thread principal
    stop = threading.Event()

    def editor_loop():
        while not stop.is_set():
            for cb in list(m._callbacks):
                if cb:
                    cb(0.016)
            time.sleep(0.005)

    thread = threading.Thread(target=editor_loop, name="EditorMainThread", daemon=True)
    thread.start()
    m._stop_editor = stop.set
    return m
