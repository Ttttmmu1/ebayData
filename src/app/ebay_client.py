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
    Supports:
      - search (item_summary/search)
      - get_item (item/{item_id}) for real description/details
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: Optional[Token] = None

    # -----------------------------
    # OAuth
    # -----------------------------
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
            body = ""
            try:
                body = r.text[:500]  # type: ignore[name-defined]
            except Exception:
                pass
            raise EbayAPIError(f"Token request failed: {e}. Body: {body}") from e
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

    # -----------------------------
    # Helpers
    # -----------------------------
    def _auth_headers(self) -> Dict[str, str]:
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.settings.marketplace_id,
        }

    def _browse_base(self) -> str:
        """
        eBay Browse API host depends on environment.
        Sandbox:    https://api.sandbox.ebay.com
        Production: https://api.ebay.com
        """
        env = (getattr(self.settings, "ebay_env", "") or "").lower()
        if env == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    # -----------------------------
    # Browse API
    # -----------------------------
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
        headers = self._auth_headers()

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

    def get_item(self, *, item_id: str, fieldgroups: str | None = None) -> Dict[str, Any]:
        """
        Browse Item API:
          GET /buy/browse/v1/item/{item_id}

        item_id looks like: v1|110588791101|0
        This endpoint returns details like shortDescription/description (if available).
        """
        headers = self._auth_headers()

        base = self._browse_base()
        url = f"{base}/buy/browse/v1/item/{item_id}"

        params: Dict[str, Any] = {}
        # optional: "PRODUCT" / "COMPACT" / etc (depends on eBay API support)
        if fieldgroups:
            params["fieldgroups"] = fieldgroups

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            body = ""
            try:
                body = r.text[:500]
            except Exception:
                pass
            raise EbayAPIError(f"Get item request failed: {e}. Body: {body}") from e
        except ValueError as e:
            raise EbayAPIError("Get item response was not valid JSON") from e