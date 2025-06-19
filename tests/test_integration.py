"""
Integration tests for Sanic-Redis
Tests the integration between Sanic and Redis functionality
"""

import pytest
import json as json_lib
from sanic import Sanic
from sanic.response import text, json
from sanic_redis import SanicRedis


class TestIntegration:
    """Test core Sanic-Redis integration functionality"""

    @pytest.mark.asyncio
    async def test_redis_connection(self, app):
        """Test Redis connection establishment"""
        @app.get("/ping")
        async def ping_handler(request):
            redis_conn = request.app.ctx.redis
            result = await redis_conn.ping()
            return json({"ping": result})

        request, response = await app.asgi_client.get("/ping")
        assert response.status_code == 200
        assert response.json["ping"] is True

    @pytest.mark.asyncio
    async def test_redis_context_availability(self, app):
        """Test Redis is available in app context"""
        @app.get("/context")
        async def handler(request):
            return json({
                "has_redis": hasattr(request.app.ctx, 'redis'),
                "redis_type": str(type(request.app.ctx.redis))
            })

        request, response = await app.asgi_client.get("/context")
        assert response.status_code == 200
        assert response.json["has_redis"] is True
        assert "Redis" in response.json["redis_type"]

    @pytest.mark.asyncio
    async def test_configuration_usage(self, app_with_config):
        """Test using Sanic config variable for Redis URL"""
        @app_with_config.get("/config")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            await redis_conn.set("config_key", "config_value")
            result = await redis_conn.get("config_key")
            return text(result.decode())

        request, response = await app_with_config.asgi_client.get("/config")
        assert response.status_code == 200
        assert response.text == "config_value"


class TestDataOperations:
    """Test Redis data operations through Sanic"""

    @pytest.mark.asyncio
    async def test_string_operations(self, app, sample_data):
        """Test string set/get operations"""
        @app.get("/string")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            key, value = "test_string", sample_data["string_key"]

            await redis_conn.set(key, value)
            result = await redis_conn.get(key)
            return text(result.decode())

        request, response = await app.asgi_client.get("/string")
        assert response.status_code == 200
        assert response.text == sample_data["string_key"]

    @pytest.mark.asyncio
    async def test_integer_operations(self, app, sample_data):
        """Test integer storage and retrieval"""
        @app.get("/integer")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            key, value = "test_int", sample_data["int_key"]

            await redis_conn.set(key, value)
            result = await redis_conn.get(key)
            return json({"value": int(result.decode())})

        request, response = await app.asgi_client.get("/integer")
        assert response.status_code == 200
        assert response.json["value"] == sample_data["int_key"]

    @pytest.mark.asyncio
    async def test_json_storage(self, app, sample_data):
        """Test JSON data storage and retrieval"""
        @app.get("/json")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            key, value = "test_json", sample_data["dict_key"]

            await redis_conn.set(key, json_lib.dumps(value))
            result = await redis_conn.get(key)
            parsed_result = json_lib.loads(result.decode())
            return json(parsed_result)

        request, response = await app.asgi_client.get("/json")
        assert response.status_code == 200
        assert response.json == sample_data["dict_key"]

    @pytest.mark.asyncio
    async def test_key_operations(self, app):
        """Test key management operations"""
        @app.get("/keys")
        async def handler(request):
            redis_conn = request.app.ctx.redis

            # Set and verify key exists
            await redis_conn.set("test_key", "test_value")
            exists_before = await redis_conn.exists("test_key")

            # Delete and verify key is gone
            deleted = await redis_conn.delete("test_key")
            exists_after = await redis_conn.exists("test_key")

            return json({
                "exists_before": bool(exists_before),
                "deleted": deleted,
                "exists_after": bool(exists_after)
            })

        request, response = await app.asgi_client.get("/keys")
        assert response.status_code == 200
        data = response.json
        assert data["exists_before"] is True
        assert data["deleted"] == 1
        assert data["exists_after"] is False

    @pytest.mark.asyncio
    async def test_key_expiration(self, app):
        """Test key expiration functionality"""
        @app.get("/expire")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            await redis_conn.setex("expire_key", 10, "expire_value")
            ttl = await redis_conn.ttl("expire_key")
            return json({"ttl": ttl})

        request, response = await app.asgi_client.get("/expire")
        assert response.status_code == 200
        assert 0 < response.json["ttl"] <= 10


class TestConnectionManagement:
    """Test connection management across requests"""

    @pytest.mark.asyncio
    async def test_data_persistence(self, app):
        """Test data persists across different requests"""
        @app.get("/set/<value>")
        async def set_handler(request, value):
            redis_conn = request.app.ctx.redis
            await redis_conn.set("persist_key", value)
            return text("set")

        @app.get("/get")
        async def get_handler(request):
            redis_conn = request.app.ctx.redis
            result = await redis_conn.get("persist_key")
            return text(result.decode() if result else "null")

        # Set value in first request
        request1, response1 = await app.asgi_client.get("/set/persistent_data")
        assert response1.status_code == 200
        assert response1.text == "set"

        # Get value in second request
        request2, response2 = await app.asgi_client.get("/get")
        assert response2.status_code == 200
        assert response2.text == "persistent_data"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, app):
        """Test multiple sequential requests"""
        @app.get("/multi/<request_id>")
        async def handler(request, request_id):
            redis_conn = request.app.ctx.redis
            key = f"multi_{request_id}"
            value = f"value_{request_id}"

            await redis_conn.set(key, value)
            result = await redis_conn.get(key)
            return text(result.decode())

        # Test multiple sequential requests
        for i in range(3):
            request, response = await app.asgi_client.get(f"/multi/{i}")
            assert response.status_code == 200
            assert response.text == f"value_{i}"


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.mark.asyncio
    async def test_redis_operation_errors(self, app):
        """Test handling of Redis operation errors"""
        @app.get("/error")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            try:
                # Set string value then try list operation (should fail)
                await redis_conn.set("test_key", "string_value")
                await redis_conn.lpush("test_key", "list_item")
                return json({"error": False})
            except Exception as e:
                return json({"error": True, "message": str(e)})

        request, response = await app.asgi_client.get("/error")
        assert response.status_code == 200
        assert response.json["error"] is True
        assert "WRONGTYPE" in response.json["message"]

    @pytest.mark.asyncio
    async def test_nonexistent_key_handling(self, app):
        """Test handling of nonexistent keys"""
        @app.get("/nonexistent")
        async def handler(request):
            redis_conn = request.app.ctx.redis
            result = await redis_conn.get("nonexistent_key_12345")
            return json({"exists": result is not None})

        request, response = await app.asgi_client.get("/nonexistent")
        assert response.status_code == 200
        assert response.json["exists"] is False

    def test_missing_configuration_error(self, app_name):
        """Test error when Redis configuration is missing"""
        my_app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(my_app)

        @my_app.get("/test")
        async def handler(request):
            return text("ok")

        with pytest.raises(ValueError, match="You must specify a redis_url"):
            _, response = my_app.test_client.get("/test")
