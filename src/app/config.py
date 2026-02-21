from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    ebay_env: str
    client_id: str
    client_secret: str
    marketplace_id: str

    @property
    def api_base(self) -> str:
        return "https://api.sandbox.ebay.com" if self.ebay_env.lower() == "sandbox" else "https://api.ebay.com"

    @property
    def oauth_token_url(self) -> str:
        return f"{self.api_base}/identity/v1/oauth2/token"

    @property
    def browse_search_url(self) -> str:
        return f"{self.api_base}/buy/browse/v1/item_summary/search"

def get_settings() -> Settings:
    env = os.getenv("EBAY_ENV", "sandbox").strip()  # sandbox|production
    cid = os.getenv("EBAY_CLIENT_ID", "").strip()
    csec = os.getenv("EBAY_CLIENT_SECRET", "").strip()
    marketplace = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip()

    if not cid or not csec:
        raise RuntimeError(
            "Missing EBAY_CLIENT_ID / EBAY_CLIENT_SECRET environment variables. "
            "Set them in your Run Configuration or terminal."
        )

    return Settings(
        ebay_env=env,
        client_id=cid,
        client_secret=csec,
        marketplace_id=marketplace,
    )
