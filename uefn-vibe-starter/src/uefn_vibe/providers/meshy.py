"""Meshy : texte -> 3D et image -> 3D (API v2 / v1)."""
from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

import httpx

from ..errors import ProviderError
from .base import new_client, raise_for_provider

BASE_URL = "https://api.meshy.ai"
ENDPOINTS = {
    "text-to-3d": "/openapi/v2/text-to-3d",
    "image-to-3d": "/openapi/v1/image-to-3d",
}
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED"}


class MeshyClient:
    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self._key = api_key
        self._client = client or new_client()

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}"}

    async def _post(self, path: str, body: dict) -> str:
        response = await self._client.post(BASE_URL + path, json=body, headers=self._headers)
        raise_for_provider(response, "Meshy")
        task_id = response.json().get("result")
        if not task_id:
            raise ProviderError("Meshy n'a pas renvoyé d'identifiant de tâche.")
        return task_id

    async def create_preview(
        self,
        prompt: str,
        *,
        target_polycount: int | None = 15000,
        ai_model: str = "latest",
        topology: str = "triangle",
    ) -> str:
        body: dict = {
            "mode": "preview",
            "prompt": prompt[:800],
            "ai_model": ai_model,
            "topology": topology,
            "should_remesh": True,
            "target_formats": ["fbx"],
        }
        if target_polycount:
            body["target_polycount"] = max(100, min(int(target_polycount), 300000))
        return await self._post(ENDPOINTS["text-to-3d"], body)

    async def create_refine(
        self, preview_task_id: str, *, texture_prompt: str | None = None, enable_pbr: bool = True
    ) -> str:
        body: dict = {
            "mode": "refine",
            "preview_task_id": preview_task_id,
            "enable_pbr": enable_pbr,
            "target_formats": ["fbx"],
        }
        if texture_prompt:
            body["texture_prompt"] = texture_prompt[:800]
        return await self._post(ENDPOINTS["text-to-3d"], body)

    async def create_image_to_3d(
        self,
        image_path: Path,
        *,
        target_polycount: int | None = 15000,
        texture_prompt: str | None = None,
        enable_pbr: bool = True,
        ai_model: str = "latest",
    ) -> str:
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        if mime not in ("image/png", "image/jpeg"):
            raise ProviderError("Meshy image->3D accepte seulement PNG ou JPEG.")
        data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        body: dict = {
            "image_url": f"data:{mime};base64,{data}",
            "ai_model": ai_model,
            "should_texture": True,
            "enable_pbr": enable_pbr,
            "should_remesh": True,
            "topology": "triangle",
            "target_formats": ["fbx"],
        }
        if target_polycount:
            body["target_polycount"] = max(100, min(int(target_polycount), 300000))
        if texture_prompt:
            body["texture_prompt"] = texture_prompt[:800]
        return await self._post(ENDPOINTS["image-to-3d"], body)

    async def get_task(self, kind: str, task_id: str) -> dict:
        response = await self._client.get(
            f"{BASE_URL}{ENDPOINTS[kind]}/{task_id}", headers=self._headers
        )
        raise_for_provider(response, "Meshy")
        return response.json()

    async def wait(
        self,
        kind: str,
        task_id: str,
        *,
        timeout_s: float,
        interval_s: float = 5.0,
        on_progress: Callable[[int], Awaitable[None]] | None = None,
    ) -> dict:
        """Attend la fin de la tâche ou renvoie la dernière photo si le délai expire."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while True:
            task = await self.get_task(kind, task_id)
            if on_progress:
                await on_progress(int(task.get("progress") or 0))
            if task.get("status") in TERMINAL or loop.time() >= deadline:
                return task
            await asyncio.sleep(interval_s)

    async def download(self, url: str, dest: Path) -> Path:
        if urlparse(url).scheme != "https":
            raise ProviderError("URL de téléchargement refusée (https obligatoire).")
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = await self._client.get(url)
        raise_for_provider(response, "Meshy (téléchargement)")
        dest.write_bytes(response.content)
        return dest
