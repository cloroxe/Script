import json
import stat
import sys

import pytest

from uefn_vibe.errors import VibeError
from uefn_vibe.setup_project import install, main


def test_install_creates_everything(project):
    result = install(project, python_exe="C:/Python311/python.exe")
    vibe = project / "VibeStarter"
    for sub in ("Models", "Audio", "Textures"):
        assert (vibe / "Inbox" / sub).is_dir()
    assert (vibe / "vibe_bridge.py").read_text().startswith('"""Pont Python')
    assert len((vibe / ".vibe_token").read_text()) >= 32
    assert "MESHY_API_KEY=" in (vibe / ".env").read_text()
    assert ".env" in (vibe / ".gitignore").read_text() and ".vibe_token" in (vibe / ".gitignore").read_text()
    assert "unreal-mcp" in (project / "AGENTS.md").read_text()
    assert (project / "CLAUDE.md").read_text().strip() == "@AGENTS.md"
    config = json.loads((project / ".mcp.json").read_text())
    assert config["mcpServers"]["unreal-mcp"] == {"type": "http", "url": "http://127.0.0.1:8000/mcp"}
    vibe_server = config["mcpServers"]["uefn-vibe"]
    assert vibe_server["command"] == "C:/Python311/python.exe"
    assert vibe_server["args"] == ["-m", "uefn_vibe.server"]
    assert vibe_server["env"] == {"UEFN_PROJECT_DIR": str(project)}
    assert result["notes"] == []


def test_mcp_json_never_contains_secrets(project):
    (project / "VibeStarter").mkdir(exist_ok=True)
    install(project)
    text = (project / ".mcp.json").read_text()
    token = (project / "VibeStarter" / ".vibe_token").read_text()
    assert token not in text and "API_KEY" not in text


@pytest.mark.skipif(sys.platform == "win32", reason="chmod POSIX")
def test_secret_files_are_private(project):
    install(project)
    for name in (".env", ".vibe_token"):
        assert stat.S_IMODE((project / "VibeStarter" / name).stat().st_mode) == 0o600


def test_install_is_idempotent_and_preserves_user_data(project):
    install(project)
    token = (project / "VibeStarter" / ".vibe_token").read_text()
    (project / "VibeStarter" / ".env").write_text("MESHY_API_KEY=keepme\n")
    (project / "AGENTS.md").write_text("MES REGLES")
    config = json.loads((project / ".mcp.json").read_text())
    config["mcpServers"]["autre"] = {"command": "x"}
    config["mcpServers"]["unreal-mcp"]["url"] = "http://127.0.0.1:9000/mcp"
    (project / ".mcp.json").write_text(json.dumps(config))

    result = install(project)
    assert (project / "VibeStarter" / ".vibe_token").read_text() == token
    assert (project / "VibeStarter" / ".env").read_text() == "MESHY_API_KEY=keepme\n"
    assert (project / "AGENTS.md").read_text() == "MES REGLES"
    assert any("AGENTS.md existe déjà" in n for n in result["notes"])
    config = json.loads((project / ".mcp.json").read_text())
    assert "autre" in config["mcpServers"]
    assert config["mcpServers"]["unreal-mcp"]["url"] == "http://127.0.0.1:9000/mcp"


def test_force_regenerates_token_and_agents(project):
    install(project)
    token = (project / "VibeStarter" / ".vibe_token").read_text()
    (project / "AGENTS.md").write_text("old")
    install(project, force=True)
    assert (project / "VibeStarter" / ".vibe_token").read_text() != token
    assert "unreal-mcp" in (project / "AGENTS.md").read_text()
    # mais les clés API de l'utilisateur ne sont jamais écrasées
    (project / "VibeStarter" / ".env").write_text("OPENAI_API_KEY=mine\n")
    install(project, force=True)
    assert (project / "VibeStarter" / ".env").read_text() == "OPENAI_API_KEY=mine\n"


def test_install_errors(tmp_path):
    with pytest.raises(VibeError, match="introuvable"):
        install(tmp_path / "nope")
    (tmp_path / ".mcp.json").write_text("{broken")
    with pytest.raises(VibeError, match="JSON valide"):
        install(tmp_path)


def test_install_warns_without_uefnproject(tmp_path):
    result = install(tmp_path)
    assert any(".uefnproject" in n for n in result["notes"])


def test_cli_main(project, capsys):
    assert main(["--project", str(project)]) == 0
    out = capsys.readouterr().out
    assert "Étapes suivantes" in out and "vibe_bridge.py" in out and "Python Editor Scripting" in out
    assert main(["--project", str(project / "missing")]) == 1
    assert "Erreur" in capsys.readouterr().err


def test_server_command_modes(monkeypatch, tmp_path):
    from uefn_vibe.setup_project import server_command
    assert server_command("C:/py.exe") == ("C:/py.exe", ["-m", "uefn_vibe.server"], None)
    assert server_command()[1] == ["-m", "uefn_vibe.server"]

    suffix = ".exe" if __import__("os").name == "nt" else ""
    setup_exe = tmp_path / ("uefn-vibe-setup" + suffix)
    setup_exe.write_bytes(b"x")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(setup_exe))
    command, args, note = server_command()
    assert command.endswith("uefn-vibe-mcp" + suffix) and args == [] and "introuvable" in note
    (tmp_path / ("uefn-vibe-mcp" + suffix)).write_bytes(b"x")
    assert server_command()[2] is None


def test_frozen_install_points_mcp_json_at_the_server_exe(monkeypatch, project, tmp_path):
    suffix = ".exe" if __import__("os").name == "nt" else ""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / ("uefn-vibe-setup" + suffix)).write_bytes(b"x")
    (bindir / ("uefn-vibe-mcp" + suffix)).write_bytes(b"x")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bindir / ("uefn-vibe-setup" + suffix)))
    install(project)
    entry = json.loads((project / ".mcp.json").read_text())["mcpServers"]["uefn-vibe"]
    assert entry["command"] == str(bindir / ("uefn-vibe-mcp" + suffix)) and entry["args"] == []


def test_cli_prompts_for_project_when_interactive(monkeypatch, project, capsys):
    monkeypatch.setattr("uefn_vibe.setup_project._interactive", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": f'"{project}"')
    assert main([]) == 0
    assert (project / "VibeStarter" / "vibe_bridge.py").is_file()


def test_cli_without_project_and_not_interactive_fails(monkeypatch, capsys):
    monkeypatch.setattr("uefn_vibe.setup_project._interactive", lambda: False)
    assert main([]) == 1
    assert "--project" in capsys.readouterr().err
