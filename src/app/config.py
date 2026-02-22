from __future__ import annotations

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    """
    Конфігурація eBay API.
    frozen=True - об'єкт незмінний після створення.
    """
    ebay_env: str # sandbox або production
    client_id: str # EBAY_CLIENT_ID
    client_secret: str # EBAY_CLIENT_SECRET
    marketplace_id: str # напр. EBAY_US

    @property
    def api_base(self) -> str:
        """Базовий URL API залежно від середовища"""
        return (
            "https://api.sandbox.ebay.com"
            if self.ebay_env.lower() == "sandbox"
            else "https://api.ebay.com"
        )

    @property
    def oauth_token_url(self) -> str:
        """URL для отримання OAuth токена"""
        return f"{self.api_base}/identity/v1/oauth2/token"

    @property
    def browse_search_url(self) -> str:
        """URL для пошуку товарів через Browse API"""
        return f"{self.api_base}/buy/browse/v1/item_summary/search"


def get_settings() -> Settings:
    """
    Зчитування налаштувань з environment variables.
    Якщо ключів немає - RuntimeError.
    """
    env = os.getenv("EBAY_ENV", "sandbox").strip() # за замовчуванням sandbox
    cid = os.getenv("EBAY_CLIENT_ID", "").strip()
    csec = os.getenv("EBAY_CLIENT_SECRET", "").strip()
    marketplace = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip()

    # перевірка обов'язкових змінних
    if not cid or not csec:
        raise RuntimeError(
            "Missing EBAY_CLIENT_ID / EBAY_CLIENT_SECRET environment variables. "
            "Set them in your Run Configuration or terminal."
        )

    # повернення об'єкта налаштувань
    return Settings(
        ebay_env=env,
        client_id=cid,
        client_secret=csec,
        marketplace_id=marketplace,
    )
