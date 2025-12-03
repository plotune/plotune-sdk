# tests/test_core.py
import asyncio
import pytest
from unittest.mock import AsyncMock

from plotune_sdk.src.core import CoreClient


class DummyRuntime:
    """A minimal dummy runtime for testing CoreClient."""
    def __init__(self):
        self.cache = {}
        self.loop = asyncio.get_event_loop()


@pytest.fixture
def dummy_runtime():
    """Provide a dummy runtime instance."""
    return DummyRuntime()


@pytest.fixture
def core_client(dummy_runtime):
    """Provide a CoreClient instance with dummy runtime."""
    client = CoreClient(runtime=dummy_runtime)
    # Mock session for async requests
    client.session = AsyncMock()
    client.core_url = "http://dummy-core.local"
    return client


@pytest.mark.asyncio
async def test_get_token(core_client):
    """Test retrieving an auth token from the dummy core."""
    # Prepare mock response
    mock_response = AsyncMock()
    mock_response.json.return_value = {
        "username": "testuser",
        "auth_token": "dummy_token",
        "valid": True
    }
    mock_response.raise_for_status.return_value = None
    core_client.session.get.return_value = mock_response

    token = await core_client.authenticator.get_token()
    assert token == "dummy_token"
    assert core_client.authenticator.authenticated is True
    assert core_client.authenticator.username == "testuser"


@pytest.mark.asyncio
async def test_get_license_token(core_client):
    """Test retrieving a license token from the dummy core."""
    # Mock get_token to ensure authenticated
    core_client.authenticator.get_token = AsyncMock(return_value="dummy_token")
    core_client.authenticator.authenticated = True
    core_client.authenticator.auth_token = "dummy_token"

    # Mock license token response
    mock_response = AsyncMock()
    mock_response.json.return_value = {"token": "license_123", "username": "testuser"}
    mock_response.raise_for_status.return_value = None
    core_client.session.get.return_value = mock_response

    username, token = await core_client.authenticator.get_license_token()
    assert username == "testuser"
    assert token == "license_123"
