from __future__ import annotations

import httpx

from ..errors import ProviderError

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=15.0)


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True)


def raise_for_provider(response: httpx.Response, provider: str) -> None:
    if response.status_code < 400:
        return
    detail = response.text[:400].replace("\n", " ")
    hint = ""
    if response.status_code == 401:
        hint = " (clé API refusée)"
    elif response.status_code == 402:
        hint = " (crédits épuisés)"
    elif response.status_code == 429:
        hint = " (trop de requêtes, réessaie plus tard)"
    raise ProviderError(f"{provider} a répondu {response.status_code}{hint}: {detail}")
