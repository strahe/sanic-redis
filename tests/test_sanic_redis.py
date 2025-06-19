"""
Tests for Sanic-Redis
Integration tests covering core functionality
"""

import pytest
from sanic import Sanic
from sanic.response import json
from sanic_redis import SanicRedis


class TestSanicRedisCore:
    """Test SanicRedis initialization, configuration, and integration with Sanic"""

    def test_initialization_patterns(self, app_name, redis_url):
        """Test all initialization patterns in one comprehensive test"""
        # Pattern 1: Basic initialization
        redis1 = SanicRedis()
        assert redis1.config_name == "REDIS"
        assert redis1.redis_url == ""
        assert redis1.single_connection_client is False

        # Pattern 2: Constructor with parameters
        redis2 = SanicRedis(config_name="CUSTOM", redis_url="redis://test:6379", single_connection_client=True)
        assert redis2.config_name == "CUSTOM"
        assert redis2.redis_url == "redis://test:6379"
        assert redis2.single_connection_client is True

        # Pattern 3: init_app method
        app = Sanic(app_name)
        redis3 = SanicRedis()
        redis3.init_app(app, config_name="INIT_APP", redis_url=redis_url, single_connection_client=True)
        assert redis3.app == app
        assert redis3.config_name == "INIT_APP"
        assert redis3.redis_url == redis_url
        assert redis3.single_connection_client is True

    def test_configuration_precedence(self, app_name, redis_url):
        """Test configuration parameter precedence rules"""
        app = Sanic(app_name)
        app.config.REDIS = "redis://config-url:6379"

        redis = SanicRedis(config_name="CONSTRUCTOR", redis_url="redis://constructor:6379")
        redis.init_app(app, config_name="INIT_APP", redis_url=redis_url)

        # init_app parameters should take precedence
        assert redis.config_name == "INIT_APP"
        assert redis.redis_url == redis_url

    @pytest.mark.asyncio
    async def test_sanic_integration(self, app_name, redis_url):
        """Test integration with Sanic application and actual Redis operations"""
        app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(app, redis_url=redis_url)

        @app.get("/test")
        async def handler(request):
            # Test Redis connection and basic operations
            redis_conn = request.app.ctx.redis

            # Test connection
            ping_result = await redis_conn.ping()

            # Test write operation
            await redis_conn.set("integration_test_key", "integration_test_value")

            # Test read operation
            value = await redis_conn.get("integration_test_key")

            # Cleanup
            await redis_conn.delete("integration_test_key")

            return json({
                "has_redis": hasattr(request.app.ctx, 'redis'),
                "ping_success": ping_result,
                "value_retrieved": value.decode() if value else None
            })

        request, response = await app.asgi_client.get("/test")
        assert response.status_code == 200
        assert response.json["has_redis"] is True
        assert response.json["ping_success"] is True
        assert response.json["value_retrieved"] == "integration_test_value"

    @pytest.mark.asyncio
    async def test_multiple_instances(self, app_name, redis_url):
        """Test multiple Redis instances in single app with actual operations"""
        app = Sanic(app_name)

        # Setup multiple instances
        app.config.REDIS_MAIN = redis_url
        redis_main = SanicRedis(config_name="REDIS_MAIN")
        redis_main.init_app(app)

        redis_cache = SanicRedis(config_name="REDIS_CACHE")
        redis_cache.init_app(app, redis_url=redis_url)

        @app.get("/multi")
        async def handler(request):
            # Test both instances can perform operations
            main_ping = await request.app.ctx.redis_main.ping()
            cache_ping = await request.app.ctx.redis_cache.ping()

            # Test operations work independently
            await request.app.ctx.redis_main.set("main_key", "main_value")
            await request.app.ctx.redis_cache.set("cache_key", "cache_value")

            main_value = await request.app.ctx.redis_main.get("main_key")
            cache_value = await request.app.ctx.redis_cache.get("cache_key")

            # Cleanup
            await request.app.ctx.redis_main.delete("main_key")
            await request.app.ctx.redis_cache.delete("cache_key")

            return json({
                "main_ping": main_ping,
                "cache_ping": cache_ping,
                "main_value": main_value.decode() if main_value else None,
                "cache_value": cache_value.decode() if cache_value else None,
                "instances_different": id(request.app.ctx.redis_main) != id(request.app.ctx.redis_cache)
            })

        request, response = await app.asgi_client.get("/multi")
        assert response.status_code == 200
        assert response.json["main_ping"] is True
        assert response.json["cache_ping"] is True
        assert response.json["main_value"] == "main_value"
        assert response.json["cache_value"] == "cache_value"
        assert response.json["instances_different"] is True

    def test_error_handling(self, app_name):
        """Test error conditions and edge cases"""
        app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(app)  # No URL provided

        @app.get("/test")
        async def handler(request):
            return json({"ok": True})

        # Should raise ValueError when no Redis URL is configured
        with pytest.raises(ValueError, match="You must specify a redis_url"):
            _, response = app.test_client.get("/test")

    @pytest.mark.asyncio
    async def test_redis_unavailable_handling(self, app_name):
        """Test behavior when Redis is unavailable"""
        app = Sanic(app_name)
        redis = SanicRedis()
        # Use invalid Redis URL
        redis.init_app(app, redis_url="redis://nonexistent-host:6379")

        @app.get("/test")
        async def handler(request):
            try:
                await request.app.ctx.redis.ping()
                return json({"status": "success"})
            except Exception as e:
                return json({"status": "error", "error_type": type(e).__name__})

        request, response = await app.asgi_client.get("/test")
        assert response.status_code == 200
        assert response.json["status"] == "error"
        # Should get connection error when Redis is unavailable
        assert "Error" in response.json["error_type"]

    def test_url_format_support(self, app_name):
        """Test various Redis URL formats are accepted"""
        app = Sanic(app_name)

        test_urls = [
            "redis://localhost:6379",
            "redis://user:pass@localhost:6379/1",
            "rediss://localhost:6379",
            "unix:///tmp/redis.sock",
            "redis://localhost:6379?socket_timeout=5&max_connections=10"
        ]

        for url in test_urls:
            redis = SanicRedis()
            redis.init_app(app, redis_url=url)
            assert redis.redis_url == url

    def test_parameter_updates(self, app_name, redis_url):
        """Test parameter update behavior during init_app"""
        app = Sanic(app_name)
        redis = SanicRedis(
            config_name="ORIGINAL",
            redis_url="redis://original:6379",
            single_connection_client=False
        )

        # Full update
        redis.init_app(app, config_name="UPDATED", redis_url=redis_url, single_connection_client=True)
        assert redis.config_name == "UPDATED"
        assert redis.redis_url == redis_url
        assert redis.single_connection_client is True

        # Partial update (None values should not override)
        redis.init_app(app, config_name=None, redis_url=None, single_connection_client=None)
        assert redis.config_name == "UPDATED"  # Should remain
        assert redis.redis_url == redis_url     # Should remain
        assert redis.single_connection_client is True  # Should remain

    def test_config_name_mapping(self, app_name):
        """Test config name to context attribute mapping"""
        app = Sanic(app_name)

        test_cases = [
            ("REDIS", "redis"),
            ("REDIS_MAIN", "redis_main"),
            ("MY_CACHE_DB", "my_cache_db")
        ]

        for config_name, expected_attr in test_cases:
            redis = SanicRedis(config_name=config_name)
            redis.init_app(app, redis_url="redis://dummy:6379")
            assert redis.config_name == config_name
            # The actual context attribute creation is tested in integration test

    def test_version_and_exports(self):
        """Test package exports and version availability"""
        from sanic_redis import SanicRedis, __version__

        # Test exports
        assert SanicRedis is not None
        assert callable(SanicRedis)
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

        # Test class attributes
        redis = SanicRedis()
        required_attrs = ['config_name', 'redis_url', 'single_connection_client', 'init_app']
        for attr in required_attrs:
            assert hasattr(redis, attr)

    @pytest.mark.asyncio
    async def test_connection_lifecycle(self, app_name, redis_url):
        """Test connection lifecycle and data persistence across requests"""
        app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(app, redis_url=redis_url)

        @app.get("/set/<value>")
        async def set_handler(request, value):
            # Set a value that should persist
            await request.app.ctx.redis.set("lifecycle_key", value)
            return json({"action": "set", "value": value})

        @app.get("/get")
        async def get_handler(request):
            # Get the value set in previous request
            value = await request.app.ctx.redis.get("lifecycle_key")
            return json({"value": value.decode() if value else None})

        @app.get("/cleanup")
        async def cleanup_handler(request):
            # Cleanup test data
            await request.app.ctx.redis.delete("lifecycle_key")
            return json({"action": "cleanup"})

        # Test data persists across different requests
        req1, resp1 = await app.asgi_client.get("/set/test_lifecycle_value")
        assert resp1.status_code == 200
        assert resp1.json["value"] == "test_lifecycle_value"

        req2, resp2 = await app.asgi_client.get("/get")
        assert resp2.status_code == 200
        assert resp2.json["value"] == "test_lifecycle_value"

        # Cleanup
        req3, resp3 = await app.asgi_client.get("/cleanup")
        assert resp3.status_code == 200
