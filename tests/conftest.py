"""
Conftest for Sanic-Redis
"""

from typing import Any, Dict
import re
import pytest

from sanic import Sanic
from sanic_redis import SanicRedis

CACHE: Dict[str, Any] = {}

slugify = re.compile(r"[^a-zA-Z0-9_\-]")


@pytest.fixture(scope="function")
def app(request):
    """
    Basic Fixture to test Sanic
    """

    my_app = Sanic(slugify.sub("-", request.node.name))
    redis = SanicRedis()
    redis.init_app(my_app, config_name="my_test_redis",
                   redis_url="redis://127.0.0.1")

    yield my_app
