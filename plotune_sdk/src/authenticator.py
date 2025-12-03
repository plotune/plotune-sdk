from functools import lru_cache


class Authenticator:
    """Handles authentication and license token retrieval for Plotune Core."""

    def __init__(self, core_client):
        from plotune_sdk.src.core import CoreClient

        self.runtime = core_client.runtime
        self.auth_token = self.runtime.cache.get("auth_token", default=None)
        self.username = self.runtime.cache.get("username", default=None)
        self.authenticated = self.auth_token is not None
        self.client: CoreClient = core_client

    @lru_cache(maxsize=None)
    async def get_token(self) -> str:
        """Retrieve or refresh the authentication token from Core."""
        if self.auth_token:
            return self.auth_token

        session = self.client.session
        auth_url = f"{self.client.core_url}/api/auth"
        response = await session.get(auth_url)
        response.raise_for_status()
        data = response.json()

        username = data.get("username")
        token = data.get("auth_token")
        valid = data.get("valid")

        if not valid:
            raise Exception("Authentication failed: Invalid credentials from Core.")

        self.auth_token = token
        self.username = username
        self.runtime.cache.set("auth_token", self.auth_token)
        self.runtime.cache.set("username", self.username)
        self.authenticated = True
        return self.auth_token

    async def get_license_token(self) -> tuple[str, str]:
        """Retrieve a license token from Core, ensuring authentication."""
        if not self.authenticated:
            await self.get_token()

        session = self.client.session
        token_url = f"{self.client.core_url}/api/token"
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        response = await session.get(token_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        token = data.get("token")
        username = data.get("username")

        if not token:
            raise Exception("Failed to retrieve license token from Core.")

        return username, token
