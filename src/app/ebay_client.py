from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from .config import Settings

SCOPE = "https://api.ebay.com/oauth/api_scope"

class EbayAPIError(RuntimeError):
    pass

@dataclass
class Token:
    access_token: str
    expires_at: float  # epoch seconds

class EbayClient:
    """
    Minimal eBay Browse API client with OAuth client_credentials token caching.
    """
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: Optional[Token] = None

    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("ascii")
        b64 = base64.b64encode(raw).decode("ascii")
        return f"Basic {b64}"

    def _fetch_token(self) -> Token:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self._basic_auth_header(),
        }
        data = {
            "grant_type": "client_credentials",
            "scope": SCOPE,
        }
        try:
            r = requests.post(self.settings.oauth_token_url, headers=headers, data=data, timeout=30)
            r.raise_for_status()
            payload = r.json()
        except requests.RequestException as e:
            raise EbayAPIError(f"Token request failed: {e}") from e
        except ValueError as e:
            raise EbayAPIError("Token response was not valid JSON") from e

        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 0)
        if not token or not expires_in:
            raise EbayAPIError(f"Unexpected token payload: {payload}")

        expires_at = time.time() + int(expires_in) - 60  # refresh 60s early
        return Token(access_token=str(token), expires_at=expires_at)

    def get_token(self) -> str:
        if self._token is None or time.time() >= self._token.expires_at:
            self._token = self._fetch_token()
        return self._token.access_token

    def search(
        self,
        *,
        q: str,
        limit: int = 20,
        offset: int = 0,
        sort: str | None = None,
        category_ids: str | None = None,
        filter_expr: str | None = None,
    ) -> Dict[str, Any]:
        token = self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.settings.marketplace_id,
        }
        params: Dict[str, Any] = {"q": q, "limit": limit, "offset": offset}
        if sort:
            params["sort"] = sort
        if category_ids:
            params["category_ids"] = category_ids
        if filter_expr:
            params["filter"] = filter_expr

        try:
            r = requests.get(self.settings.browse_search_url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            body = ""
            try:
                body = r.text[:500]
            except Exception:
                pass
            raise EbayAPIError(f"Search request failed: {e}. Body: {body}") from e
        except ValueError as e:
            raise EbayAPIError("Search response was not valid JSON") from e
