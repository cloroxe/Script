import io
import json
import wave

import pytest

from uefn_vibe import kit
from uefn_vibe.audio import pcm16_to_wav
from uefn_vibe.building import MAX_PLACEMENTS, plan_building, summarize
from uefn_vibe.config import Settings, load_settings
from uefn_vibe.errors import MissingKey, VibeError
from uefn_vibe.library import Library
from uefn_vibe.paths import ensure_within, safe_name


def test_safe_name():
    assert safe_name("Ma super épée!") == "Ma_super_p_e"
    assert safe_name("3dTree") == "A_3dTree"
    assert safe_name("x", prefix="SM_") == "SM_x"
    with pytest.raises(VibeError):
        safe_name("!!!")


def test_ensure_within_blocks_traversal(tmp_path):
    base = tmp_path / "VibeStarter"
    base.mkdir()
    assert ensure_within(base, base / "Inbox" / "a.wav")
    with pytest.raises(VibeError):
        ensure_within(base, base / ".." / "secret.txt")
    with pytest.raises(VibeError):
        ensure_within(base, tmp_path / "other.txt")


def test_pcm_to_wav_is_valid_wav():
    pcm = b"\x00\x01" * 4410
    wav = pcm16_to_wav(pcm, 44100)
    with wave.open(io.BytesIO(wav)) as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 44100
        assert handle.getnframes() == 4410


def test_pcm_odd_length_is_trimmed():
    wav = pcm16_to_wav(b"\x00\x01\x02", 24000)
    with wave.open(io.BytesIO(wav)) as handle:
        assert handle.getnframes() == 1


def test_settings_repr_and_redact_hide_keys():
    s = Settings(meshy_api_key="abc123", bridge_token="tok")
    assert "abc123" not in repr(s)
    assert s.redact("fail abc123 tok") == "fail *** ***"
    with pytest.raises(MissingKey):
        Settings().require("OPENAI_API_KEY")


def test_load_settings_reads_env_file_and_token(project):
    (project / "VibeStarter" / ".env").write_text('MESHY_API_KEY="from-file"\nOPENAI_IMAGE_MODEL=gpt-image-2\n# c\n')
    (project / "VibeStarter" / ".vibe_token").write_text("tok\n")
    s = load_settings({"UEFN_PROJECT_DIR": str(project), "OPENAI_API_KEY": "from-env"})
    assert s.meshy_api_key == "from-file"
    assert s.openai_api_key == "from-env"
    assert s.openai_image_model == "gpt-image-2"
    assert s.bridge_token == "tok"
    assert s.content_root == "/MyIsland"
    assert s.key_status() == {"MESHY_API_KEY": True, "ELEVENLABS_API_KEY": False, "OPENAI_API_KEY": True}


def test_env_overrides_file(project):
    (project / "VibeStarter" / ".env").write_text("MESHY_API_KEY=file\n")
    s = load_settings({"UEFN_PROJECT_DIR": str(project), "MESHY_API_KEY": "env"})
    assert s.meshy_api_key == "env"


def test_vibe_dir_requires_project():
    with pytest.raises(VibeError):
        Settings().vibe_dir


def test_library_roundtrip_and_corrupt_file(tmp_path):
    lib = Library(tmp_path / "VibeStarter" / "library.json")
    assert lib.all() == {}
    lib.put("A", {"status": "pending"})
    assert lib.update("A", status="done")["status"] == "done"
    assert lib.get("A") == {"status": "done"}
    (tmp_path / "VibeStarter" / "library.json").write_text("{not json")
    assert lib.all() == {}


def test_plan_building_counts():
    plan = plan_building(width_cm=800, depth_cm=1200, floors=2, module_cm=400)
    counts = summarize(plan)
    # 2 x 3 modules : 2*(2+3)=10 murs/étage, dont 1 porte au RDC
    assert counts == {"floor": 12, "doorway": 1, "wall": 19, "roof": 6}


def test_plan_building_geometry_and_rotation():
    plan = plan_building(width_cm=400, depth_cm=400, module_cm=400, roof=False, floor_slab=False, door=False)
    walls = {tuple(p["location"][:2]): p["rotation"][1] for p in plan}
    assert walls[(0.0, -200.0)] == 0.0 and walls[(0.0, 200.0)] == 0.0
    assert walls[(-200.0, 0.0)] == 90.0 and walls[(200.0, 0.0)] == 90.0
    rotated = plan_building(width_cm=400, depth_cm=400, module_cm=400, yaw_deg=90, roof=False, floor_slab=False, door=False)
    front = next(p for p in rotated if p["location"][0] == 200.0)  # mur y=-200 tourné de 90° -> x=+200
    assert front["rotation"][1] == 90.0


def test_plan_building_origin_and_limits():
    plan = plan_building(width_cm=400, depth_cm=400, origin=(1000, 2000, 50), roof=False, floor_slab=False, door=False)
    assert all(p["location"][2] == 50 for p in plan)
    assert any(p["location"][1] == 2000 - 200 for p in plan)
    with pytest.raises(VibeError):
        plan_building(width_cm=0, depth_cm=400)
    with pytest.raises(VibeError):
        plan_building(width_cm=400 * 60, depth_cm=400 * 60, floors=2)
    assert MAX_PLACEMENTS == 2000


def test_kit_templates_and_guides():
    assert set(kit.list_templates()) >= {"vibe_hud", "vibe_menu"}
    code = kit.render_template("vibe_hud", "mon hud")
    assert "mon_hud := class(creative_device)" in code and "__CLASS_NAME__" not in code
    assert set(kit.list_guides()) >= {"workflow", "assets", "verse_ui", "umg_verse_fields", "building"}
    assert "unreal-mcp" in kit.read_agents_md()
    with pytest.raises(VibeError):
        kit.read_template("../../etc/passwd")
    with pytest.raises(VibeError):
        kit.read_guide("nope")


def test_max_generations_setting(project):
    assert load_settings({"UEFN_PROJECT_DIR": str(project)}).max_generations == 50
    assert load_settings({"UEFN_PROJECT_DIR": str(project), "VIBE_MAX_GENERATIONS": "7"}).max_generations == 7
    assert load_settings({"UEFN_PROJECT_DIR": str(project), "VIBE_MAX_GENERATIONS": "abc"}).max_generations == 50
    assert load_settings({"UEFN_PROJECT_DIR": str(project), "VIBE_MAX_GENERATIONS": "0"}).max_generations == 1
