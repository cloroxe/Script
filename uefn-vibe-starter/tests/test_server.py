import io
import json
import wave

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from uefn_vibe.server import mcp

from conftest import KEY, body, json_response, png_b64

MESHY = "https://api.meshy.ai/openapi"


async def call(tool, /, **arguments):
    content, structured = await mcp.call_tool(tool, arguments)
    return structured


def meshy_task(status, progress=100, **extra):
    return {"status": status, "progress": progress, **extra}


@pytest.fixture
def meshy_ok(web):
    """Meshy simulé : preview t1 -> refine r1 -> FBX + textures téléchargeables."""
    web.add("POST", f"{MESHY}/v2/text-to-3d",
            lambda r: json_response({"result": "t1" if body(r)["mode"] == "preview" else "r1"}))
    web.add("GET", f"{MESHY}/v2/text-to-3d/t1", lambda r: json_response(meshy_task("SUCCEEDED")))
    web.add("GET", f"{MESHY}/v2/text-to-3d/r1", lambda r: json_response(meshy_task(
        "SUCCEEDED",
        model_urls={"fbx": "https://assets.meshy.ai/r1.fbx"},
        texture_urls=[{"base_color": "https://assets.meshy.ai/r1_bc.png", "normal": "https://assets.meshy.ai/r1_n.png"}],
    )))
    web.add("GET", "https://assets.meshy.ai/", lambda r: httpx.Response(200, content=b"BIN:" + r.url.path.encode()))


async def test_tools_registered_without_leaking_context_param():
    tools = {t.name: t for t in await mcp.list_tools()}
    assert {"vibe_status", "meshy_text_to_3d", "meshy_check", "elevenlabs_sound_effect", "openai_icon",
            "build_structure", "import_to_uefn", "verse_template", "uefn_guide"} <= set(tools)
    assert "ctx" not in tools["meshy_text_to_3d"].inputSchema["properties"]


async def test_status_reports_keys_without_values(runtime, bridge_ok, web):
    web.add("GET", "http://127.0.0.1:8000/mcp", lambda r: httpx.Response(406))
    status = await call("vibe_status")
    assert status["keys"] == {"MESHY_API_KEY": True, "ELEVENLABS_API_KEY": True, "OPENAI_API_KEY": True}
    assert status["bridge"]["reachable"] is True and status["official_mcp"]["reachable"] is True
    assert KEY not in json.dumps(status)


async def test_status_when_everything_is_offline(runtime):
    status = await call("vibe_status")
    assert status["bridge"]["reachable"] is False and "vibe_bridge.py" in status["bridge"]["hint"]
    assert status["official_mcp"]["reachable"] is False


async def test_meshy_text_to_3d_full_pipeline(runtime, web, meshy_ok, bridge_ok, project):
    result = await call("meshy_text_to_3d", prompt="mossy rock", name="rock", wait_seconds=30)
    assert result["status"] == "done"
    fbx = project / "VibeStarter" / "Inbox" / "Models" / "SM_rock.fbx"
    assert fbx.read_bytes() == b"BIN:/r1.fbx"
    assert (project / "VibeStarter" / "Inbox" / "Textures" / "SM_rock_base_color.png").is_file()

    # preview PUIS refine (texture), et refine pointe bien vers la preview
    posts = [body(r) for r in web.sent("POST", f"{MESHY}/v2/text-to-3d")]
    assert [p["mode"] for p in posts] == ["preview", "refine"] and posts[1]["preview_task_id"] == "t1"

    imports = [c for c in bridge_ok if c["command"] == "import_assets"]
    assert len(imports) == 1
    items = {i["name"]: i for i in imports[0]["payload"]["items"]}
    assert items["SM_rock"]["dest_path"] == "/MyIsland/VibeStarter/Models" and items["SM_rock"]["kind"] == "model"
    assert items["SM_rock_base_color"]["dest_path"] == "/MyIsland/VibeStarter/Textures"
    library = await call("library_list")
    assert library["SM_rock"]["status"] == "done"


async def test_meshy_untextured_skips_refine(runtime, web, meshy_ok, bridge_ok):
    web.routes.insert(0, ("GET", f"{MESHY}/v2/text-to-3d/t1", lambda r: json_response(
        meshy_task("SUCCEEDED", model_urls={"fbx": "https://assets.meshy.ai/t1.fbx"}))))
    result = await call("meshy_text_to_3d", prompt="crate", name="crate", textured=False, wait_seconds=30)
    assert result["status"] == "done"
    assert [body(r)["mode"] for r in web.sent("POST", f"{MESHY}/v2/text-to-3d")] == ["preview"]


async def test_meshy_pending_then_resume_with_check(runtime, web, meshy_ok, bridge_ok):
    state = {"calls": 0}

    def slow_preview(request):
        state["calls"] += 1
        return json_response(meshy_task("IN_PROGRESS", 30) if state["calls"] == 1 else meshy_task("SUCCEEDED"))

    web.routes.insert(0, ("GET", f"{MESHY}/v2/text-to-3d/t1", slow_preview))
    first = await call("meshy_text_to_3d", prompt="tree", name="tree", wait_seconds=0)
    assert first["status"] == "pending" and "meshy_check" in first["next"]
    # un nom en cours ne peut pas être réutilisé
    with pytest.raises(ToolError, match="existe déjà"):
        await call("meshy_text_to_3d", prompt="tree", name="tree")
    done = await call("meshy_check", name="tree", wait_seconds=30)
    assert done["status"] == "done"


async def test_meshy_failure_is_reported_and_name_reusable(runtime, web, meshy_ok):
    web.routes.insert(0, ("GET", f"{MESHY}/v2/text-to-3d/t1", lambda r: json_response(
        meshy_task("FAILED", task_error={"message": "bad prompt"}))))
    result = await call("meshy_text_to_3d", prompt="x", name="bad", wait_seconds=5)
    assert result["status"] == "failed" and result["error"] == "bad prompt"
    web.routes.insert(0, ("GET", f"{MESHY}/v2/text-to-3d/t1", lambda r: json_response(meshy_task("IN_PROGRESS", 1))))
    again = await call("meshy_text_to_3d", prompt="x", name="bad", wait_seconds=0)
    assert again["status"] == "pending"


async def test_meshy_without_key_gives_actionable_error(settings, web):
    from dataclasses import replace
    from uefn_vibe.server import Runtime, set_runtime
    set_runtime(Runtime(replace(settings, meshy_api_key=None), http=web.client()))
    with pytest.raises(ToolError, match="VibeStarter/.env"):
        await call("meshy_text_to_3d", prompt="x", name="y")
    set_runtime(None)


async def test_import_falls_back_to_manual_when_bridge_is_down(runtime, web, meshy_ok, project):
    result = await call("meshy_text_to_3d", prompt="rock", name="rock", wait_seconds=30)
    assert result["status"] == "done"  # rien n'est perdu
    assert result["import"]["imported"] is False
    manual = result["import"]["manual_import"]
    assert manual[0]["drag_into"] == "/MyIsland/VibeStarter/Models"
    assert (project / "VibeStarter" / "Inbox" / "Models" / "SM_rock.fbx").is_file()


async def test_elevenlabs_sound_effect_end_to_end(runtime, web, bridge_ok, project):
    web.add("POST", "https://api.elevenlabs.io/v1/sound-generation", lambda r: httpx.Response(200, content=b"\x00\x01" * 2205))
    result = await call("elevenlabs_sound_effect", prompt="door slam", name="door", duration_seconds=1)
    wav_path = project / "VibeStarter" / "Inbox" / "Audio" / "SFX_door.wav"
    with wave.open(str(wav_path)) as handle:
        assert handle.getframerate() == 44100
    assert result["import"]["imported"] is True
    item = bridge_ok[-1]["payload"]["items"][0]
    assert item["kind"] == "audio" and item["dest_path"] == "/MyIsland/VibeStarter/Audio"


async def test_elevenlabs_speech_uses_voice_prefix(runtime, web, bridge_ok, project):
    web.add("POST", "https://api.elevenlabs.io/v1/text-to-speech/VoiceX", lambda r: httpx.Response(200, content=b"\x00\x01" * 100))
    await call("elevenlabs_speech", text="Bienvenue", name="intro", voice_id="VoiceX")
    assert (project / "VibeStarter" / "Inbox" / "Audio" / "VO_intro.wav").is_file()


async def test_openai_icon_end_to_end(runtime, web, bridge_ok, project):
    web.add("POST", "https://api.openai.com/v1/images/generations", lambda r: json_response({"data": [{"b64_json": png_b64()}]}))
    result = await call("openai_icon", subject="golden key", name="key")
    assert (project / "VibeStarter" / "Inbox" / "Textures" / "T_Icon_key.png").read_bytes().startswith(b"\x89PNG")
    prompt = body(web.sent("POST", "https://api.openai.com")[0])["prompt"]
    assert "golden key" in prompt and "no text" in prompt
    assert result["import"]["imported"] is True


async def test_provider_error_never_leaks_the_key(runtime, web):
    web.add("POST", "https://api.openai.com", lambda r: httpx.Response(400, text=f"bad request for {KEY}"))
    with pytest.raises(ToolError) as error:
        await call("openai_icon", subject="x", name="y", import_to_uefn=False)
    assert KEY not in str(error.value) and "***" in str(error.value)


async def test_import_to_uefn_rejects_paths_outside_vibestarter(runtime, bridge_ok, project, tmp_path_factory):
    outside = project / "secret.fbx"
    outside.write_bytes(b"x")
    with pytest.raises(ToolError, match="hors du projet"):
        await call("import_to_uefn", files=[{"path": str(outside), "kind": "model", "name": "leak"}])
    with pytest.raises(ToolError, match="hors du projet"):
        await call("import_to_uefn", files=[{"path": "VibeStarter/../secret.fbx", "kind": "model", "name": "leak"}])
    assert not bridge_ok


async def test_import_to_uefn_validates_extension_and_kind(runtime, bridge_ok, project):
    exe = project / "VibeStarter" / "Inbox" / "a.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    with pytest.raises(ToolError, match="non importable"):
        await call("import_to_uefn", files=[{"path": str(exe), "kind": "model", "name": "a"}])
    with pytest.raises(ToolError, match="kind inconnu"):
        await call("import_to_uefn", files=[{"path": str(exe), "kind": "script", "name": "a"}])


async def test_import_to_uefn_relative_path_ok(runtime, bridge_ok, project):
    wav = project / "VibeStarter" / "Inbox" / "Audio" / "x.wav"
    wav.parent.mkdir(parents=True)
    wav.write_bytes(b"RIFF")
    result = await call("import_to_uefn", files=[{"path": "VibeStarter/Inbox/Audio/x.wav", "kind": "audio", "name": "my sound"}])
    assert result["imported"] is True
    assert bridge_ok[-1]["payload"]["items"][0]["name"] == "my_sound"


async def test_image_to_3d_only_reads_inside_vibestarter(runtime, web, meshy_ok, bridge_ok, project):
    web.add("POST", f"{MESHY}/v1/image-to-3d", lambda r: json_response({"result": "i1"}))
    web.add("GET", f"{MESHY}/v1/image-to-3d/i1", lambda r: json_response(
        meshy_task("SUCCEEDED", model_urls={"fbx": "https://assets.meshy.ai/i1.fbx"})))
    outside = project / "private.png"
    outside.write_bytes(b"\x89PNG")
    with pytest.raises(ToolError, match="hors du projet"):
        await call("meshy_image_to_3d", image_path=str(outside), name="leak")
    assert not web.sent("POST", f"{MESHY}/v1/image-to-3d")  # rien n'a été envoyé à Meshy

    inside = project / "VibeStarter" / "Inbox" / "Textures" / "concept.png"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"\x89PNGdata")
    result = await call("meshy_image_to_3d", image_path="VibeStarter/Inbox/Textures/concept.png", name="thing", wait_seconds=30)
    assert result["status"] == "done"


async def test_build_structure_dry_run_then_spawn(runtime, bridge_ok):
    args = dict(width_cm=800, depth_cm=800, wall_asset="/MyIsland/VibeStarter/Models/SM_wall",
                floor_asset="/MyIsland/VibeStarter/Models/SM_floor", doorway_asset="/MyIsland/VibeStarter/Models/SM_door")
    dry = await call("build_structure", **args)
    assert dry["dry_run"] is True and dry["pieces"] == {"floor": 4, "doorway": 1, "wall": 7} and dry["total"] == 12
    assert not bridge_ok  # aucun acteur posé en dry_run

    real = await call("build_structure", dry_run=False, origin=[100, 200, 0], **args)
    spawn = bridge_ok[-1]
    assert spawn["command"] == "spawn_actors" and len(spawn["payload"]["items"]) == 12
    assert real["spawned"]["spawned"] == 12
    assert {i["asset"] for i in spawn["payload"]["items"]} == {args["wall_asset"], args["floor_asset"], args["doorway_asset"]}


async def test_build_structure_rejects_bad_origin_and_oversize(runtime, bridge_ok):
    with pytest.raises(ToolError, match="origin"):
        await call("build_structure", width_cm=400, depth_cm=400, wall_asset="/A/b", origin=[1, 2])
    with pytest.raises(ToolError, match="trop gros"):
        await call("build_structure", width_cm=400 * 80, depth_cm=400 * 80, wall_asset="/A/b")


async def test_verse_template_listing_render_and_write(runtime, project):
    assert "vibe_hud" in (await call("verse_template"))["templates"]
    preview = await call("verse_template", name="vibe_menu", class_name="shop_menu")
    assert "shop_menu := class(creative_device)" in preview["code"] and "written" not in preview

    content = project / "Plugins" / "MyIsland" / "Content"
    content.mkdir(parents=True)
    written = await call("verse_template", name="vibe_hud", class_name="score_hud", write_to_project=True)
    assert written["written"] is True and (content / "score_hud.verse").is_file()
    with pytest.raises(ToolError, match="existe déjà"):
        await call("verse_template", name="vibe_hud", class_name="score_hud", write_to_project=True)


async def test_verse_template_without_verse_folder_returns_code(runtime):
    result = await call("verse_template", name="vibe_hud", class_name="h", write_to_project=True)
    assert result["written"] is False and "hint" in result


async def test_uefn_guide(runtime):
    topics = (await call("uefn_guide"))["topics"]
    assert "umg_verse_fields" in topics
    guide = await call("uefn_guide", topic="umg_verse_fields")
    assert "View Bindings" in guide["content"]


async def test_generation_budget_blocks_runaway_loops(settings, web, bridge_ok):
    from dataclasses import replace
    from uefn_vibe.server import Runtime, set_runtime
    web.add("POST", "https://api.openai.com", lambda r: json_response({"data": [{"b64_json": png_b64()}]}))
    set_runtime(Runtime(replace(settings, max_generations=2), http=web.client()))
    try:
        await call("openai_icon", subject="a", name="a")
        await call("openai_icon", subject="b", name="b")
        with pytest.raises(ToolError, match="Plafond de 2 générations"):
            await call("openai_icon", subject="c", name="c")
        assert len(web.sent("POST", "https://api.openai.com")) == 2  # le 3e appel n'est jamais parti
        assert (await call("vibe_status"))["generations"] == {"used": 2, "limit": 2}
        # les lectures / vérifications ne consomment pas le plafond
        await call("library_list")
    finally:
        set_runtime(None)


async def test_meshy_check_does_not_consume_budget(runtime, web, meshy_ok, bridge_ok):
    await call("meshy_text_to_3d", prompt="x", name="rock", wait_seconds=30)
    used = runtime.generations
    await call("meshy_check", name="rock")
    assert runtime.generations == used == 1
