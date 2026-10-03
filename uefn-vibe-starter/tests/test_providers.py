import base64
import io
import wave

import httpx
import pytest

from uefn_vibe.errors import ProviderError
from uefn_vibe.providers.elevenlabs import ElevenLabsClient
from uefn_vibe.providers.meshy import MeshyClient
from uefn_vibe.providers.openai_images import OpenAIImageClient

from conftest import body, json_response, png_b64


async def test_meshy_preview_request_shape(web):
    web.add("POST", "https://api.meshy.ai/openapi/v2/text-to-3d", lambda r: json_response({"result": "t1"}))
    client = MeshyClient("mk", web.client())
    assert await client.create_preview("a mossy rock", target_polycount=999999) == "t1"
    request = web.requests[0]
    assert request.headers["Authorization"] == "Bearer mk"
    data = body(request)
    assert data["mode"] == "preview" and data["target_polycount"] == 300000
    assert data["target_formats"] == ["fbx"] and data["should_remesh"] is True


async def test_meshy_refine_and_image_requests(web, tmp_path):
    web.add("POST", "https://api.meshy.ai/openapi/v2/text-to-3d", lambda r: json_response({"result": "r1"}))
    web.add("POST", "https://api.meshy.ai/openapi/v1/image-to-3d", lambda r: json_response({"result": "i1"}))
    client = MeshyClient("mk", web.client())
    assert await client.create_refine("t1", texture_prompt="mossy") == "r1"
    refine = body(web.requests[0])
    assert refine["mode"] == "refine" and refine["preview_task_id"] == "t1" and refine["enable_pbr"] is True

    image = tmp_path / "a.png"
    image.write_bytes(b"\x89PNGdata")
    assert await client.create_image_to_3d(image) == "i1"
    assert body(web.requests[1])["image_url"].startswith("data:image/png;base64,")
    (tmp_path / "a.gif").write_bytes(b"GIF")
    with pytest.raises(ProviderError):
        await client.create_image_to_3d(tmp_path / "a.gif")


async def test_meshy_errors_are_readable(web):
    web.add("POST", "https://api.meshy.ai", lambda r: httpx.Response(402, text="no credits"))
    with pytest.raises(ProviderError, match="crédits épuisés"):
        await MeshyClient("mk", web.client()).create_preview("x")


async def test_meshy_wait_returns_snapshot_on_timeout(web):
    web.add("GET", "https://api.meshy.ai/openapi/v2/text-to-3d/t1",
            lambda r: json_response({"status": "IN_PROGRESS", "progress": 40}))
    seen = []

    async def progress(value):
        seen.append(value)

    task = await MeshyClient("mk", web.client()).wait("text-to-3d", "t1", timeout_s=0, on_progress=progress)
    assert task["status"] == "IN_PROGRESS" and seen == [40]


async def test_meshy_download_requires_https(web, tmp_path):
    with pytest.raises(ProviderError):
        await MeshyClient("mk", web.client()).download("http://evil.example/a.fbx", tmp_path / "a.fbx")
    web.add("GET", "https://assets.meshy.ai/a.fbx", lambda r: httpx.Response(200, content=b"FBX"))
    path = await MeshyClient("mk", web.client()).download("https://assets.meshy.ai/a.fbx", tmp_path / "x" / "a.fbx")
    assert path.read_bytes() == b"FBX"


async def test_elevenlabs_sfx_request_and_wav(web):
    pcm = b"\x01\x00" * 100
    web.add("POST", "https://api.elevenlabs.io/v1/sound-generation", lambda r: httpx.Response(200, content=pcm))
    wav = await ElevenLabsClient("ek", web.client()).sound_effect(
        "door slam", duration_seconds=99, prompt_influence=2, loop=True
    )
    request = web.requests[0]
    assert request.headers["xi-api-key"] == "ek"
    assert request.url.params["output_format"] == "pcm_44100"
    assert body(request) == {"text": "door slam", "duration_seconds": 30.0, "prompt_influence": 1.0, "loop": True}
    with wave.open(io.BytesIO(wav)) as handle:
        assert handle.getframerate() == 44100 and handle.getnframes() == 100


async def test_elevenlabs_falls_back_to_lower_sample_rate(web):
    def handler(request):
        if request.url.params["output_format"] == "pcm_44100":
            return httpx.Response(403, text="pcm_44100 requires pro tier")
        return httpx.Response(200, content=b"\x00\x00" * 10)

    web.add("POST", "https://api.elevenlabs.io", handler)
    wav = await ElevenLabsClient("ek", web.client()).sound_effect("rain")
    with wave.open(io.BytesIO(wav)) as handle:
        assert handle.getframerate() == 24000


async def test_elevenlabs_bad_key_is_not_retried(web):
    web.add("POST", "https://api.elevenlabs.io", lambda r: httpx.Response(401, text="bad key"))
    with pytest.raises(ProviderError, match="clé API refusée"):
        await ElevenLabsClient("ek", web.client()).sound_effect("rain")
    assert len(web.requests) == 1


async def test_elevenlabs_all_rates_rejected_raises_first_error(web):
    web.add("POST", "https://api.elevenlabs.io", lambda r: httpx.Response(422, text="invalid"))
    with pytest.raises(ProviderError, match="422"):
        await ElevenLabsClient("ek", web.client()).sound_effect("rain")
    assert len(web.requests) == 3


async def test_elevenlabs_speech_validates_voice_id(web):
    web.add("POST", "https://api.elevenlabs.io/v1/text-to-speech/Voice123", lambda r: httpx.Response(200, content=b"\x00\x00"))
    client = ElevenLabsClient("ek", web.client())
    await client.speech("Bonjour", "Voice123")
    assert body(web.requests[0]) == {"text": "Bonjour", "model_id": "eleven_multilingual_v2"}
    with pytest.raises(ProviderError):
        await client.speech("x", "../../admin")


async def test_openai_image_request_and_decode(web):
    web.add("POST", "https://api.openai.com/v1/images/generations",
            lambda r: json_response({"data": [{"b64_json": png_b64()}]}))
    png = await OpenAIImageClient("ok", "gpt-image-1", web.client()).generate_png("a sword")
    assert png.startswith(b"\x89PNG")
    request = web.requests[0]
    assert request.headers["Authorization"] == "Bearer ok"
    data = body(request)
    assert data["model"] == "gpt-image-1" and data["background"] == "transparent"
    assert data["output_format"] == "png" and "response_format" not in data


async def test_openai_validation_and_empty_response(web):
    client = OpenAIImageClient("ok", "gpt-image-1", web.client())
    with pytest.raises(ProviderError):
        await client.generate_png("x", size="64x64")
    with pytest.raises(ProviderError):
        await client.generate_png("x", quality="ultra")
    web.add("POST", "https://api.openai.com", lambda r: json_response({"data": []}))
    with pytest.raises(ProviderError, match="aucune image"):
        await client.generate_png("x")
