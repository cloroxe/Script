"""Bout en bout : outils MCP -> vrai client HTTP -> vrai pont (faux `unreal`)."""
import importlib.util
import sys

import pytest
from mcp.server.fastmcp.exceptions import ToolError

import fake_unreal
from uefn_vibe.config import load_settings
from uefn_vibe.server import Runtime, mcp, set_runtime
from uefn_vibe.setup_project import install


@pytest.fixture
def live(project):
    install(project)
    unreal = fake_unreal.build()
    sys.modules["unreal"] = unreal
    spec = importlib.util.spec_from_file_location("vb_e2e", project / "VibeStarter" / "vibe_bridge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    state = module.start(port=0)
    port = state.server.server_address[1]
    settings = load_settings({"UEFN_PROJECT_DIR": str(project), "VIBE_BRIDGE_URL": f"http://127.0.0.1:{port}"})
    set_runtime(Runtime(settings))  # vrai httpx, pas de mock
    yield unreal
    set_runtime(None)
    state.stop()
    unreal._stop_editor()
    sys.modules.pop("unreal", None)


async def call(tool, /, **arguments):
    return (await mcp.call_tool(tool, arguments))[1]


async def test_status_sees_the_live_bridge(live):
    status = await call("vibe_status")
    assert status["bridge"]["reachable"] is True
    assert status["bridge"]["info"]["bridge"] == "vibe_bridge"


async def test_import_to_uefn_through_real_bridge(live, project):
    fbx = project / "VibeStarter" / "Inbox" / "Models" / "SM_rock.fbx"
    fbx.write_bytes(b"FBX")
    result = await call("import_to_uefn", files=[{"path": str(fbx), "kind": "model", "name": "SM_rock"}])
    assert result["imported"] is True
    assert result["assets"][0]["object_paths"] == ["/MyIsland/VibeStarter/Models/SM_rock"]
    assert live.imported[0]["destination_path"] == "/MyIsland/VibeStarter/Models"


async def test_build_structure_through_real_bridge(live):
    result = await call(
        "build_structure", width_cm=800, depth_cm=800, wall_asset="/MyIsland/VibeStarter/Models/SM_wall",
        floors=2, dry_run=False, origin=[0, 0, 100],
    )
    assert result["spawned"]["spawned"] == result["total"] == 16
    assert len(live.spawned) == 16 and live.spawned[0].label == "Building_000"
    assert all(a.loc[3] in (100.0, 400.0) for a in live.spawned)


async def test_wrong_token_surfaces_as_unavailable_not_crash(live, project):
    (project / "VibeStarter" / ".vibe_token").write_text("rotated")
    set_runtime(Runtime(load_settings({"UEFN_PROJECT_DIR": str(project),
                                       "VIBE_BRIDGE_URL": get_url(live)})))
    fbx = project / "VibeStarter" / "Inbox" / "Models" / "SM_a.fbx"
    fbx.write_bytes(b"FBX")
    result = await call("import_to_uefn", files=[{"path": str(fbx), "kind": "model", "name": "SM_a"}])
    assert result["imported"] is False and "jeton" in result["reason"].lower()
    with pytest.raises(ToolError, match="jeton"):
        await call("save_project")


def get_url(unreal):
    # l'URL du pont vivant est celle de la fixture `live` (port éphémère) : on la relit via le serveur
    import threading  # noqa: F401
    state = unreal._vibe_bridge_state
    return f"http://127.0.0.1:{state.server.server_address[1]}"
