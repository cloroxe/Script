"""Client du pont Python qui tourne DANS UEFN (bridge/vibe_bridge.py)."""
from __future__ import annotations

from typing import Any

import httpx

from .errors import BridgeUnavailable, VibeError


class BridgeClient:
    def __init__(self, url: str, token: str | None, client: httpx.AsyncClient | None = None):
        self._url = url.rstrip("/")
        self._token = token
        self._client = client or httpx.AsyncClient()

    async def call(self, command: str, payload: dict[str, Any] | None = None) -> Any:
        if not self._token:
            raise BridgeUnavailable(
                "Jeton du pont absent (VibeStarter/.vibe_token). Relance `uefn-vibe-setup`."
            )
        try:
            response = await self._client.post(
                f"{self._url}/rpc",
                json={"command": command, "payload": payload or {}},
                headers={"X-Vibe-Token": self._token},
                timeout=httpx.Timeout(130.0, connect=3.0),
            )
        except httpx.TransportError as error:
            raise BridgeUnavailable(
                "Le pont UEFN ne répond pas. Dans UEFN, exécute VibeStarter/vibe_bridge.py "
                f"(console de sortie : py \"<chemin>\\vibe_bridge.py\"). Détail : {type(error).__name__}"
            ) from None
        if response.status_code == 401:
            raise BridgeUnavailable("Le pont a refusé le jeton : relance le pont après `uefn-vibe-setup`.")
        data = response.json()
        if not data.get("ok"):
            raise VibeError(f"Pont UEFN : {data.get('error', 'erreur inconnue')}")
        return data.get("result")
