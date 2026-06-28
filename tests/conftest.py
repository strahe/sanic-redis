"""
Test fixtures for Sanic-Redis.
"""

import os
import re

import pytest
from redis.asyncio import from_url

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
TEST_REDIS_DB = int(os.getenv("TEST_REDIS_DB", "15"))

slugify = re.compile(r"[^a-zA-Z0-9_\-]")


@pytest.fixture
def app_name(request):
    """Generate a unique Sanic app name for each test."""
    return slugify.sub("-", request.node.nodeid)


@pytest.fixture
def redis_url():
    """Build the Redis URL used by integration tests."""
    return f"{REDIS_URL.rstrip('/')}/{TEST_REDIS_DB}"


@pytest.fixture
async def redis_server(redis_url):
    """Fail quickly when integration Redis is unavailable."""
    redis = from_url(redis_url)
    try:
        await redis.ping()
    except Exception as exc:
        pytest.fail(
            "Redis is required for integration tests. "
            "Start it with: docker compose -f docker-compose.test.yml up -d. "
            f"Connection failed with {type(exc).__name__}: {exc}"
        )
    finally:
        await redis.aclose()


@pytest.fixture
async def redis_key(redis_url, redis_server, request):
    """Create isolated Redis keys and clean up only keys used by the test."""
    prefix = f"sanic-redis:{slugify.sub('-', request.node.nodeid)}"
    keys = []

    def build_key(name):
        key = f"{prefix}:{name}"
        keys.append(key)
        return key

    yield build_key

    if not keys:
        return

    redis = from_url(redis_url)
    try:
        await redis.delete(*keys)
    finally:
        await redis.aclose()
