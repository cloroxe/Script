import base64
import json

import httpx
import pytest

from uefn_vibe.config import Settings
from uefn_vibe.server import Runtime, set_runtime

KEY = "sk-test-SECRET-123"


class FakeWeb:
    """Routeur HTTP en mémoire : (méthode, préfixe d'URL) -> handler(request) -> Response."""

    def __init__(self):
        self.routes = []
        self.requests = []

    def add(self, method, prefix, handler):
        self.routes.append((method, prefix, handler))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        for method, prefix, handler in self.routes:
            if request.method == method and url.startswith(prefix):
                return handler(request)
        raise httpx.ConnectError("hors ligne (aucune route)", request=request)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))

    def sent(self, method, prefix):
        return [r for r in self.requests if r.method == method and str(r.url).startswith(prefix)]


def json_response(data, status=200):
    return httpx.Response(status, json=data)


def body(request: httpx.Request):
    return json.loads(request.content)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "MyIsland.uefnproject").write_text("{}")
    (tmp_path / "VibeStarter").mkdir()
    return tmp_path


@pytest.fixture
def settings(project):
    return Settings(
        project_dir=project,
        content_root="/MyIsland",
        meshy_api_key=KEY,
        elevenlabs_api_key=KEY,
        openai_api_key=KEY,
        bridge_token="bridge-token",
    )


@pytest.fixture
def web():
    return FakeWeb()


@pytest.fixture
def runtime(settings, web):
    rt = Runtime(settings, http=web.client())
    set_runtime(rt)
    yield rt
    set_runtime(None)


@pytest.fixture
def bridge_ok(web):
    """Pont UEFN simulé : accepte tout et enregistre les commandes."""
    calls = []

    def handler(request):
        data = body(request)
        calls.append(data)
        if data["command"] == "import_assets":
            result = [
                {"name": i["name"], "kind": i["kind"], "object_paths": [f"{i['dest_path']}/{i['name']}"], "ok": True}
                for i in data["payload"]["items"]
            ]
        elif data["command"] == "spawn_actors":
            result = {"spawned": len(data["payload"]["items"]), "failed": []}
        else:
            result = {"bridge": "fake"}
        return json_response({"ok": True, "result": result})

    web.add("POST", "http://127.0.0.1:8765/rpc", handler)
    return calls


def png_b64() -> str:
    return base64.b64encode(b"\x89PNG\r\n\x1a\nFAKE").decode()
