"""
Test configuration for Sanic-Redis
Provides fixtures and utilities for testing
"""

import os
import re

import pytest
from sanic import Sanic

from sanic_redis import SanicRedis

# Redis configuration for tests
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379")
TEST_REDIS_DB = int(os.getenv("TEST_REDIS_DB", "15"))

slugify = re.compile(r"[^a-zA-Z0-9_\-]")


@pytest.fixture
def app_name(request):
    """Generate a unique app name for each test"""
    return slugify.sub("-", request.node.name)


@pytest.fixture
def redis_url():
    """Get Redis URL for testing"""
    return f"{REDIS_URL}/{TEST_REDIS_DB}"


@pytest.fixture
def basic_app(app_name):
    """Basic Sanic app without Redis configured"""
    return Sanic(app_name)


@pytest.fixture
def app(app_name, redis_url):
    """Sanic app with Redis configured using URL parameter"""
    my_app = Sanic(app_name)
    redis = SanicRedis()
    redis.init_app(my_app, redis_url=redis_url)
    return my_app


@pytest.fixture
def app_with_config(app_name, redis_url):
    """Sanic app with Redis configured using config variable"""
    my_app = Sanic(app_name)
    my_app.config.REDIS = redis_url
    redis = SanicRedis()
    redis.init_app(my_app)
    return my_app
