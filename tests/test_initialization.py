"""
Initialization tests for Sanic-Redis
Tests SanicRedis initialization, configuration, and setup
"""

import pytest
from sanic import Sanic
from sanic.response import json, text
from sanic_redis import SanicRedis


class TestSanicRedisInitialization:
    """Test SanicRedis initialization patterns"""

    def test_init_without_app(self):
        """Test creating SanicRedis instance without app"""
        redis = SanicRedis()
        assert redis.config_name == "REDIS"
        assert redis.redis_url == ""
        assert redis.single_connection_client is False

    def test_init_with_app_and_url(self, app_name, redis_url):
        """Test creating SanicRedis with app and URL during initialization"""
        my_app = Sanic(app_name)
        redis = SanicRedis(app=my_app, redis_url=redis_url)

        assert redis.app == my_app
        assert redis.redis_url == redis_url

    def test_init_app_method(self, app_name, redis_url):
        """Test init_app method"""
        my_app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(my_app, redis_url=redis_url)

        assert redis.app == my_app
        assert redis.redis_url == redis_url

    def test_init_app_with_custom_config_name(self, app_name, redis_url):
        """Test init_app with custom config name"""
        my_app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(my_app, config_name="CUSTOM_REDIS", redis_url=redis_url)

        assert redis.config_name == "CUSTOM_REDIS"
        assert redis.redis_url == redis_url

    def test_multiple_initialization_patterns(self, app_name, redis_url):
        """Test different initialization patterns work correctly"""
        # Pattern 1: init_app after instance creation
        app1 = Sanic(f"{app_name}_1")
        redis1 = SanicRedis()
        redis1.init_app(app1, redis_url=redis_url)
        assert redis1.app == app1

        # Pattern 2: pass app during instance creation
        app2 = Sanic(f"{app_name}_2")
        redis2 = SanicRedis(app=app2, redis_url=redis_url)
        assert redis2.app == app2


class TestSanicRedisConfiguration:
    """Test SanicRedis configuration options"""

    @pytest.mark.asyncio
    async def test_config_from_sanic_config(self, app_name, redis_url):
        """Test reading Redis URL from Sanic config"""
        my_app = Sanic(app_name)
        my_app.config.REDIS = redis_url

        redis = SanicRedis()
        redis.init_app(my_app)

        @my_app.get("/test")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            result = await redis_conn.ping()
            return json({"ping": result})

        request, response = await my_app.asgi_client.get("/test")
        assert response.status_code == 200
        assert response.json["ping"] is True

    @pytest.mark.asyncio
    async def test_custom_config_name(self, app_name, redis_url):
        """Test custom config name"""
        my_app = Sanic(app_name)
        my_app.config.CUSTOM_REDIS = redis_url

        redis = SanicRedis()
        redis.init_app(my_app, config_name="CUSTOM_REDIS")

        @my_app.get("/test")
        async def handler(request):
            # With custom config name "CUSTOM_REDIS", the connection is stored as "custom_redis"
            redis_conn = request.app.ctx.custom_redis
            result = await redis_conn.ping()
            return json({"ping": result})

        request, response = await my_app.asgi_client.get("/test")
        assert response.status_code == 200
        assert response.json["ping"] is True

    @pytest.mark.asyncio
    async def test_single_connection_client_option(self, app_name, redis_url):
        """Test single_connection_client option"""
        my_app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(my_app, redis_url=redis_url, single_connection_client=True)

        assert redis.single_connection_client is True

        @my_app.get("/test")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            result = await redis_conn.ping()
            return json({"ping": result})

        request, response = await my_app.asgi_client.get("/test")
        assert response.status_code == 200
        assert response.json["ping"] is True

    def test_url_precedence(self, app_name, redis_url):
        """Test that explicit redis_url takes precedence over config"""
        my_app = Sanic(app_name)
        my_app.config.REDIS = "redis://invalid-url:6379"

        redis = SanicRedis()
        redis.init_app(my_app, redis_url=redis_url)

        # Should use the explicit redis_url, not the config value
        assert redis.redis_url == redis_url


class TestSanicRedisLifecycle:
    """Test SanicRedis lifecycle integration"""

    @pytest.mark.asyncio
    async def test_redis_context_setup(self, app):
        """Test that Redis context is properly set up"""
        @app.get("/lifecycle")
        async def handler(request):
            return json({
                "has_redis": hasattr(request.app.ctx, 'redis'),
                "redis_available": request.app.ctx.redis is not None
            })

        request, response = await app.asgi_client.get("/lifecycle")
        assert response.status_code == 200
        assert response.json["has_redis"] is True
        assert response.json["redis_available"] is True

    @pytest.mark.asyncio
    async def test_redis_connection_ready(self, app):
        """Test that Redis connection is ready for use"""
        @app.get("/ready")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            try:
                await redis_conn.ping()
                return json({"ready": True})
            except Exception as e:
                return json({"ready": False, "error": str(e)})

        request, response = await app.asgi_client.get("/ready")
        assert response.status_code == 200
        assert response.json["ready"] is True


class TestSanicRedisErrorHandling:
    """Test error handling during initialization"""

    def test_missing_redis_url_error(self, app_name):
        """Test error when no Redis URL is provided"""
        my_app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(my_app)

        @my_app.get("/test")
        async def handler(request):
            return text("ok")

        with pytest.raises(ValueError, match="You must specify a redis_url"):
            _, response = my_app.test_client.get("/test")

    def test_invalid_redis_url_configuration(self, app_name):
        """Test handling of invalid Redis URL during configuration"""
        my_app = Sanic(app_name)
        redis = SanicRedis()

        # Should not raise error during init_app
        redis.init_app(my_app, redis_url="redis://invalid-host:9999")

        # Configuration should be set even with invalid URL
        assert redis.redis_url == "redis://invalid-host:9999"

    def test_missing_config_key(self, app_name):
        """Test error when config key is missing"""
        my_app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(my_app, config_name="NONEXISTENT_CONFIG")

        @my_app.get("/test")
        async def handler(request):
            return text("ok")

        with pytest.raises(ValueError, match="You must specify a redis_url"):
            _, response = my_app.test_client.get("/test")


class TestSanicRedisCompatibility:
    """Test version and compatibility information"""

    def test_version_available(self):
        """Test that version information is available"""
        from sanic_redis import __version__
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_required_exports(self):
        """Test that required exports are available"""
        from sanic_redis import SanicRedis, __version__

        assert SanicRedis is not None
        assert __version__ is not None
        assert callable(SanicRedis)

    def test_sanic_redis_attributes(self):
        """Test SanicRedis class has expected attributes"""
        redis = SanicRedis()

        # Check default attribute values
        assert hasattr(redis, 'config_name')
        assert hasattr(redis, 'redis_url')
        assert hasattr(redis, 'single_connection_client')

        # Check methods exist
        assert hasattr(redis, 'init_app')
        assert callable(redis.init_app)

        # Check default values
        assert redis.config_name == "REDIS"
        assert redis.redis_url == ""
        assert redis.single_connection_client is False
