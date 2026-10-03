"""OpenAI Images : icônes PNG (fond transparent possible) avec gpt-image-1."""
from __future__ import annotations

import base64

import httpx

from ..errors import ProviderError
from .base import new_client, raise_for_provider

URL = "https://api.openai.com/v1/images/generations"
SIZES = {"1024x1024", "1536x1024", "1024x1536"}
QUALITIES = {"low", "medium", "high"}


class OpenAIImageClient:
    def __init__(self, api_key: str, model: str = "gpt-image-1", client: httpx.AsyncClient | None = None):
        self._key = api_key
        self._model = model
        self._client = client or new_client()

    async def generate_png(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        quality: str = "medium",
        transparent: bool = True,
    ) -> bytes:
        if size not in SIZES:
            raise ProviderError(f"size doit valoir l'un de {sorted(SIZES)}")
        if quality not in QUALITIES:
            raise ProviderError(f"quality doit valoir l'un de {sorted(QUALITIES)}")
        body = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": 1,
            "output_format": "png",
            "background": "transparent" if transparent else "opaque",
        }
        # Les modèles gpt-image renvoient toujours b64_json : ne pas envoyer response_format.
        response = await self._client.post(
            URL, json=body, headers={"Authorization": f"Bearer {self._key}"}, timeout=180.0
        )
        raise_for_provider(response, "OpenAI")
        items = response.json().get("data") or []
        if not items or not items[0].get("b64_json"):
            raise ProviderError("OpenAI n'a renvoyé aucune image.")
        return base64.b64decode(items[0]["b64_json"])
