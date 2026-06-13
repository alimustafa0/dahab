"""GoldAPI.io HTTP client — the ONLY place that talks to the live API."""

import requests
from django.conf import settings


class GoldApiError(Exception):
    """Raised when GoldAPI returns an error or is unreachable."""


class GoldApiClient:
    def __init__(self, api_key=None, base_url=None, timeout=15):
        self.api_key = api_key or settings.GOLDAPI_KEY
        self.base_url = (base_url or settings.GOLDAPI_BASE_URL).rstrip("/")
        self.timeout = timeout
        if not self.api_key:
            raise GoldApiError("GOLDAPI_KEY is not set. Add it to your .env file.")

    def _headers(self):
        return {"x-access-token": self.api_key, "Content-Type": "application/json"}

    def fetch_quote(self, currency):
        """Fetch the current XAU quote in `currency` ('USD' or 'EGP'). Returns the raw JSON dict."""
        url = f"{self.base_url}/XAU/{currency.upper()}"
        try:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise GoldApiError(f"Network error calling GoldAPI: {exc}") from exc

        if response.status_code != 200:
            raise GoldApiError(f"GoldAPI returned {response.status_code}: {response.text[:200]}")

        data = response.json()
        # GoldAPI sometimes signals errors with a 200 + an "error" field.
        if "error" in data:
            raise GoldApiError(f"GoldAPI error: {data['error']}")
        return data