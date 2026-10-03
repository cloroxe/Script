import importlib.util
import json
import sys
import urllib.error
import urllib.request

import pytest

import fake_unreal
from uefn_vibe.setup_project import install


@pytest.fixture
def bridge(project):
    """Installe le projet puis charge le pont INSTALLÉ avec un faux `unreal`, comme dans UEFN."""
    install(project)
    unreal = fake_unreal.build()
    sys.modules["unreal"] = unreal
    path = project / "VibeStarter" / "vibe_bridge.py"
    spec = importlib.util.spec_from_file_location("vibe_bridge_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = module.start(port=0)
    module.url = f"http://127.0.0.1:{state.server.server_address[1]}/rpc"
    module.token = (project / "VibeStarter" / ".vibe_token").read_text().strip()
    module.unreal_fake = unreal
    yield module
    state.stop()
    unreal._stop_editor()
    sys.modules.pop("unreal", None)


def rpc(bridge, command, payload=None, *, token="__ok__", headers=None, raw=None):
    data = raw if raw is not None else json.dumps({"command": command, "payload": payload or {}}).encode()
    request = urllib.request.Request(bridge.url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if token == "__ok__":
        token = bridge.token
    if token is not None:
        request.add_header("X-Vibe-Token", token)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_ping_and_main_thread_execution(bridge, project):
    status, reply = rpc(bridge, "ping")
    assert status == 200 and reply["ok"] and reply["result"]["bridge"] == "vibe_bridge"
    assert reply["result"]["root"].endswith("VibeStarter")

    wav = project / "VibeStarter" / "Inbox" / "Audio" / "SFX_a.wav"
    wav.write_bytes(b"RIFF")
    status, reply = rpc(bridge, "import_assets", {"items": [
        {"file": str(wav), "dest_path": "/MyIsland/VibeStarter/Audio", "name": "SFX_a", "kind": "audio"}]})
    assert reply["ok"] and reply["result"][0]["object_paths"] == ["/MyIsland/VibeStarter/Audio/SFX_a"]
    # l'API Unreal n'est JAMAIS appelée depuis le thread HTTP
    assert set(bridge.unreal_fake.thread_names) == {"EditorMainThread"}


def test_rejects_missing_or_wrong_token(bridge):
    assert rpc(bridge, "ping", token=None)[0] == 401
    assert rpc(bridge, "ping", token="nope")[0] == 401
    assert not bridge.unreal_fake.imported


def test_rejects_foreign_host_header(bridge):
    status, reply = rpc(bridge, "ping", headers={"Host": "evil.example"})
    assert status == 403 and reply["ok"] is False


def test_rejects_non_json_and_bad_requests(bridge):
    request = urllib.request.Request(bridge.url, data=b"x", method="POST")
    request.add_header("X-Vibe-Token", bridge.token)
    request.add_header("Content-Type", "text/plain")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=5)
    assert error.value.code == 415
    assert rpc(bridge, "ping", raw=b"{not json")[0] == 400
    assert rpc(bridge, "does_not_exist")[0] == 400
    assert rpc(bridge, "ping", raw=b"[1,2]")[0] == 400


def test_rejects_oversized_body(bridge):
    # Le pont répond 413 sans lire le corps : selon le timing, le client voit le 413
    # ou une coupure de connexion. Dans les deux cas la requête est refusée.
    try:
        status, _ = rpc(bridge, "ping", raw=b"{" + b" " * 2_100_000 + b"}")
        assert status == 413
    except (urllib.error.URLError, ConnectionError):
        pass
    assert rpc(bridge, "ping")[0] == 200  # le pont reste vivant


def test_get_is_not_served(bridge):
    request = urllib.request.Request(bridge.url, method="GET")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(request, timeout=5)
    assert error.value.code == 501


@pytest.mark.parametrize("make", [
    lambda p, d: {"file": str(p.parent.parent.parent / "outside.wav"), "dest_path": d, "name": "x", "kind": "audio"},
    lambda p, d: {"file": str(p) + "/../../../outside.wav", "dest_path": d, "name": "x", "kind": "audio"},
    lambda p, d: {"file": str(p), "dest_path": "/Game/../Evil", "name": "x", "kind": "audio"},
    lambda p, d: {"file": str(p), "dest_path": d, "name": "../x", "kind": "audio"},
    lambda p, d: {"file": str(p), "dest_path": d, "name": "x", "kind": "model"},   # .wav n'est pas un modèle
    lambda p, d: {"file": str(p), "dest_path": d, "name": "x", "kind": "script"},
])
def test_import_validation(bridge, project, make):
    (project / "outside.wav").write_bytes(b"x")
    wav = project / "VibeStarter" / "Inbox" / "Audio" / "a.wav"
    wav.write_bytes(b"RIFF")
    status, reply = rpc(bridge, "import_assets", {"items": [make(wav, "/MyIsland/VibeStarter/Audio")]})
    assert reply["ok"] is False
    assert not bridge.unreal_fake.imported


def test_model_import_sets_fbx_options(bridge, project):
    fbx = project / "VibeStarter" / "Inbox" / "Models" / "SM_a.fbx"
    fbx.write_bytes(b"FBX")
    _, reply = rpc(bridge, "import_assets", {"items": [
        {"file": str(fbx), "dest_path": "/MyIsland/VibeStarter/Models", "name": "SM_a", "kind": "model"}]})
    assert reply["ok"]
    task = bridge.unreal_fake.imported[0]
    assert task["replace_existing"] is True and task["automated"] is True and task["save"] is True
    options = task["options"]
    assert options.props["import_as_skeletal"] is False and options.props["import_mesh"] is True
    assert options.static_mesh_import_data.props["combine_meshes"] is True


def test_failed_import_is_reported_per_item(bridge, project):
    wav = project / "VibeStarter" / "Inbox" / "Audio" / "a.wav"
    wav.write_bytes(b"RIFF")
    _, reply = rpc(bridge, "import_assets", {"items": [
        {"file": str(wav), "dest_path": "/MyIsland/VibeStarter/Audio", "name": "will_fail", "kind": "audio"}]})
    assert reply["ok"] and reply["result"][0]["ok"] is False


def test_spawn_actors(bridge):
    items = [
        {"asset": "/MyIsland/VibeStarter/Models/SM_wall", "location": [100, 200, 0], "rotation": [0, 90, 0], "scale": [1, 1, 2]},
        {"asset": "/MyIsland/Missing/SM_none"},
        {"asset": "/MyIsland/VibeStarter/Models/SM_wall"},
    ]
    _, reply = rpc(bridge, "spawn_actors", {"items": items, "label_prefix": "Hut house!"})
    assert reply["ok"] and reply["result"]["spawned"] == 2
    assert reply["result"]["failed"][0]["index"] == 1
    first = bridge.unreal_fake.spawned[0]
    assert first.loc == ("vec", 100.0, 200.0, 0.0)
    assert first.rot == ("rot", 0.0, 0.0, 90.0)  # (roll, pitch, yaw)
    assert first.scale == ("vec", 1.0, 1.0, 2.0)
    assert [a.label for a in bridge.unreal_fake.spawned] == ["Hut_house__000", "Hut_house__002"]


@pytest.mark.parametrize("items", [
    [{"asset": "../../etc/passwd"}],
    [{"asset": "/A/b", "location": [1, 2]}],
    [{"asset": "/A/b", "location": ["a", "b", "c"]}],
    [],
    [{"asset": "/A/b"}] * 2001,
])
def test_spawn_validation(bridge, items):
    _, reply = rpc(bridge, "spawn_actors", {"items": items})
    assert reply["ok"] is False
    assert not bridge.unreal_fake.spawned


def test_save_all(bridge):
    _, reply = rpc(bridge, "save_all")
    assert reply["result"] == {"saved": True} and bridge.unreal_fake.saved == [(True, True)]


def test_restart_replaces_previous_instance(bridge, project):
    state = bridge.start(port=0)
    new_url = f"http://127.0.0.1:{state.server.server_address[1]}/rpc"
    bridge.url = new_url
    assert rpc(bridge, "ping")[0] == 200
    state.stop()


def test_refuses_to_start_without_token(project):
    install(project)
    (project / "VibeStarter" / ".vibe_token").unlink()
    unreal = fake_unreal.build()
    sys.modules["unreal"] = unreal
    try:
        spec = importlib.util.spec_from_file_location("vb2", project / "VibeStarter" / "vibe_bridge.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with pytest.raises(module.BridgeError, match="Jeton"):
            module.start(port=0)
    finally:
        unreal._stop_editor()
        sys.modules.pop("unreal", None)
