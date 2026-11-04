"""
GitHub App Authentication and Installation Token Management.
Generates RS256 JWTs and exchanges them for short-lived installation access tokens.
Falls back seamlessly to GITHUB_TOKEN if App credentials are not configured.
"""

import os
import time
from typing import Any

import httpx
import jwt

from app.config import Settings, get_settings
from app.core.errors import GitHubAPIError
from app.core.logging import logger


class GitHubAppAuthManager:
    """Manages GitHub App authentication, JWT minting, and installation token caching."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._token_cache: dict[str, dict[str, Any]] = {}

    def _load_private_key(self) -> str | None:
        """Resolves GitHub App private key from environment variable or file path."""
        key_raw = self.settings.GITHUB_APP_PRIVATE_KEY
        if not key_raw:
            return None

        # Check if key is a file path
        if os.path.isfile(key_raw):
            try:
                with open(key_raw, encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read GitHub App private key file: {e}")
                return None

        # Otherwise treat key_raw as PEM string content (fixing escaped newlines if needed)
        return key_raw.replace("\\n", "\n").strip()

    def generate_app_jwt(self) -> str:
        """Mints a short-lived (10 min) RS256 JWT signed by the GitHub App private key."""
        if not self.settings.GITHUB_APP_ID:
            raise GitHubAPIError("GITHUB_APP_ID is required to generate GitHub App JWT.")

        private_key = self._load_private_key()
        if not private_key:
            raise GitHubAPIError("GITHUB_APP_PRIVATE_KEY is missing or invalid.")

        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60s in the past to allow for clock drift
            "exp": now + (9 * 60),  # Valid for 9 minutes
            "iss": str(self.settings.GITHUB_APP_ID),
        }

        try:
            token = jwt.encode(payload, private_key, algorithm="RS256")
            return token
        except Exception as e:
            logger.error(f"Failed to sign GitHub App JWT: {e}")
            raise GitHubAPIError(f"JWT signing failed: {str(e)}")

    async def get_installation_access_token(self, installation_id: str | int) -> str:
        """Retrieves or refreshes an installation access token for a given GitHub App installation.

        Falls back to GITHUB_TOKEN if GitHub App credentials are not configured.
        """
        inst_id_str = str(installation_id)

        # Check in-memory cache first
        cached = self._token_cache.get(inst_id_str)
        now = time.time()
        if cached and cached.get("expires_at", 0) > (now + 60):
            return cached["token"]

        # If App ID or Private Key is absent, fall back to Personal Access Token
        if not self.settings.GITHUB_APP_ID or not self.settings.GITHUB_APP_PRIVATE_KEY:
            if self.settings.GITHUB_TOKEN:
                logger.info("Using GITHUB_TOKEN fallback for installation access.")
                return self.settings.GITHUB_TOKEN
            raise GitHubAPIError("Neither GitHub App credentials nor GITHUB_TOKEN are configured.")

        # Mint App JWT and request installation access token from GitHub
        app_jwt = self.generate_app_jwt()
        url = f"{self.settings.GITHUB_API_BASE_URL.rstrip('/')}/app/installations/{inst_id_str}/access_tokens"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {app_jwt}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CodeSentra-PR-Reviewer",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers)
                if response.is_error:
                    raise GitHubAPIError(
                        f"Failed to fetch installation token for ID {inst_id_str}: {response.text[:200]}",
                        status_code=response.status_code,
                    )
                data = response.json()
                token = data["token"]
                # Cache token for 55 minutes
                self._token_cache[inst_id_str] = {
                    "token": token,
                    "expires_at": now + (55 * 60),
                }
                logger.info(f"Generated new installation token for installation ID {inst_id_str}")
                return token
        except httpx.RequestError as exc:
            logger.error(f"Network error fetching installation access token: {exc}")
            raise GitHubAPIError(f"Network error contacting GitHub API: {str(exc)}")
