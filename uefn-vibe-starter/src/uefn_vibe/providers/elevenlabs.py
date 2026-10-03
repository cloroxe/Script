"""ElevenLabs : effets sonores (sound-generation) et voix (text-to-speech)."""
from __future__ import annotations

import httpx

from ..audio import pcm16_to_wav
from ..errors import ProviderError
from .base import new_client, raise_for_provider

BASE_URL = "https://api.elevenlabs.io"
# 44.1 kHz peut être réservé à certains forfaits : on retombe sur des débits plus bas.
PCM_RATES = (44100, 24000, 22050)
_FALLBACK_STATUS = {400, 403, 422}


class ElevenLabsClient:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self._key = api_key
        self._client = client or new_client()

    async def _pcm_request(self, path: str, body: dict) -> bytes:
        """POST + conversion du PCM s16le en WAV, avec repli sur un débit plus bas."""
        first_error: ProviderError | None = None
        for rate in PCM_RATES:
            response = await self._client.post(
                f"{BASE_URL}{path}",
                params={"output_format": f"pcm_{rate}"},
                json=body,
                headers={"xi-api-key": self._key},
            )
            if response.status_code in _FALLBACK_STATUS:
                try:
                    raise_for_provider(response, "ElevenLabs")
                except ProviderError as error:
                    first_error = first_error or error
                continue
            raise_for_provider(response, "ElevenLabs")
            return pcm16_to_wav(response.content, rate)
        assert first_error is not None
        raise first_error

    async def sound_effect(
        self,
        text: str,
        *,
        duration_seconds: float | None = None,
        prompt_influence: float | None = None,
        loop: bool = False,
    ) -> bytes:
        body: dict = {"text": text}
        if duration_seconds is not None:
            body["duration_seconds"] = max(0.5, min(float(duration_seconds), 30.0))
        if prompt_influence is not None:
            body["prompt_influence"] = max(0.0, min(float(prompt_influence), 1.0))
        if loop:
            body["loop"] = True
        return await self._pcm_request("/v1/sound-generation", body)

    async def speech(
        self, text: str, voice_id: str, *, model_id: str = "eleven_multilingual_v2"
    ) -> bytes:
        if not voice_id.replace("-", "").replace("_", "").isalnum():
            raise ProviderError("voice_id invalide.")
        return await self._pcm_request(
            f"/v1/text-to-speech/{voice_id}", {"text": text, "model_id": model_id}
        )
