"""
Tests for the Sanic-Redis plugin behavior.
"""

from importlib.metadata import version

import pytest
from sanic import Sanic
from sanic.response import json

import sanic_redis.core as core
from sanic_redis import SanicRedis, __version__


class FakeRedis:
    def __init__(self):
        self.closed = False
        self.url = None

    async def aclose(self):
        self.closed = True


def get_listener(app, event):
    return next(
        listener.listener
        for listener in app._future_listeners
        if listener.event == event
    )


class TestSanicRedisUnit:
    def test_initializes_with_defaults_and_custom_values(self):
        redis = SanicRedis()

        assert redis.config_name == "REDIS"
        assert redis.redis_url == ""
        assert redis.single_connection_client is False
        assert redis.auto_close_connection_pool is None
        assert redis.app is None
        assert redis.conn is None

        custom = SanicRedis(
            config_name="CACHE",
            redis_url="redis://example:6379/1",
            single_connection_client=True,
            auto_close_connection_pool=False,
        )

        assert custom.config_name == "CACHE"
        assert custom.redis_url == "redis://example:6379/1"
        assert custom.single_connection_client is True
        assert custom.auto_close_connection_pool is False

    def test_init_app_updates_only_explicit_parameters(self, app_name, redis_url):
        app = Sanic(app_name)
        redis = SanicRedis(
            config_name="ORIGINAL",
            redis_url="redis://original:6379/0",
            single_connection_client=True,
            auto_close_connection_pool=True,
        )

        redis.init_app(
            app,
            config_name="UPDATED",
            redis_url=redis_url,
            single_connection_client=False,
            auto_close_connection_pool=False,
        )

        assert redis.app is app
        assert redis.config_name == "UPDATED"
        assert redis.redis_url == redis_url
        assert redis.single_connection_client is False
        assert redis.auto_close_connection_pool is False

        redis.init_app(
            app,
            config_name=None,
            redis_url=None,
            single_connection_client=None,
            auto_close_connection_pool=None,
        )

        assert redis.config_name == "UPDATED"
        assert redis.redis_url == redis_url
        assert redis.single_connection_client is False
        assert redis.auto_close_connection_pool is False

    def test_package_exports_public_objects(self):
        assert SanicRedis is not None
        assert callable(SanicRedis)
        assert isinstance(__version__, str)
        assert __version__

        redis = SanicRedis()
        for attr in (
            "config_name",
            "redis_url",
            "single_connection_client",
            "auto_close_connection_pool",
            "init_app",
        ):
            assert hasattr(redis, attr)


class TestSanicRedisStartup:
    @pytest.mark.asyncio
    async def test_startup_uses_config_url_and_closes_client(
        self, app_name, monkeypatch
    ):
        fake = FakeRedis()
        calls = []

        def fake_from_url(url, **kwargs):
            calls.append((url, kwargs))
            return fake

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        app.config.REDIS_CACHE = "redis://config:6379/1"
        redis = SanicRedis(config_name="REDIS_CACHE", single_connection_client=True)
        redis.init_app(app)

        @app.get("/")
        async def handler(request):
            return json(
                {
                    "ctx_has_client": request.app.ctx.redis_cache is fake,
                    "plugin_has_client": redis.conn is fake,
                }
            )

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {"ctx_has_client": True, "plugin_has_client": True}
        assert calls == [
            (
                "redis://config:6379/1",
                {"single_connection_client": True},
            )
        ]
        assert fake.closed is True

    @pytest.mark.asyncio
    async def test_startup_uses_init_app_url_and_explicit_false(
        self, app_name, redis_url, monkeypatch
    ):
        fake = FakeRedis()
        calls = []

        def fake_from_url(url, **kwargs):
            calls.append((url, kwargs))
            return fake

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        app.config.REDIS = "redis://config:6379/1"
        redis = SanicRedis(single_connection_client=True)
        redis.init_app(
            app,
            redis_url=redis_url,
            single_connection_client=False,
            auto_close_connection_pool=False,
        )

        @app.get("/")
        async def handler(request):
            return json({"ctx_has_client": request.app.ctx.redis is fake})

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {"ctx_has_client": True}
        assert calls == [
            (
                redis_url,
                {
                    "single_connection_client": False,
                    "auto_close_connection_pool": False,
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_startup_requires_redis_url_or_config(self, app_name):
        app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(app)

        @app.get("/")
        async def handler(_request):
            return json({"ok": True})

        with pytest.raises(ValueError, match="REDIS Sanic config variable"):
            await app.asgi_client.get("/")

    @pytest.mark.asyncio
    async def test_reused_extension_closes_current_app_connection(
        self, app_name, monkeypatch
    ):
        clients = []

        def fake_from_url(url, **kwargs):
            client = FakeRedis()
            client.url = url
            clients.append(client)
            return client

        monkeypatch.setattr(core, "from_url", fake_from_url)

        redis = SanicRedis()
        first_app = Sanic(f"{app_name}-first")
        second_app = Sanic(f"{app_name}-second")

        redis.init_app(first_app, redis_url="redis://first:6379/0")
        redis.init_app(second_app, redis_url="redis://second:6379/0")

        await get_listener(first_app, "before_server_start")(first_app)
        await get_listener(second_app, "before_server_start")(second_app)

        first_client = first_app.ctx.redis
        second_client = second_app.ctx.redis

        assert [client.url for client in clients] == [
            "redis://first:6379/0",
            "redis://second:6379/0",
        ]

        await get_listener(first_app, "after_server_stop")(first_app)

        assert first_client.closed is True
        assert second_client.closed is False
        assert redis.conn is second_client

        await get_listener(second_app, "after_server_stop")(second_app)

        assert second_client.closed is True
        assert redis.conn is None


class TestSanicRedisIntegration:
    @pytest.mark.asyncio
    @pytest.mark.compat
    @pytest.mark.integration
    async def test_compatibility_smoke(self, app_name, redis_url, redis_key):
        assert version("sanic").split(".", 1)[0] == "25"
        assert version("redis").split(".", 1)[0] == "6"
        assert version("hiredis").split(".", 1)[0] == "3"
        assert callable(core.from_url)

        app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(app, redis_url=redis_url)
        key = redis_key("smoke")

        @app.get("/")
        async def handler(request):
            client = request.app.ctx.redis
            await client.set(key, "smoke-value")
            value = await client.get(key)
            await client.delete(key)
            return json(
                {
                    "ctx_has_client": client is redis.conn,
                    "ping": await client.ping(),
                    "value": value.decode(),
                }
            )

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {
            "ctx_has_client": True,
            "ping": True,
            "value": "smoke-value",
        }

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_configured_url_supports_basic_commands(
        self, app_name, redis_url, redis_key
    ):
        app = Sanic(app_name)
        app.config.REDIS = redis_url
        redis = SanicRedis()
        redis.init_app(app)
        key = redis_key("configured")

        @app.get("/")
        async def handler(request):
            await request.app.ctx.redis.set(key, "configured-value")
            value = await request.app.ctx.redis.get(key)
            await request.app.ctx.redis.delete(key)
            return json({"value": value.decode()})

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {"value": "configured-value"}

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_instances_use_separate_clients(
        self, app_name, redis_url, redis_key
    ):
        app = Sanic(app_name)
        app.config.REDIS_MAIN = redis_url
        main = SanicRedis(config_name="REDIS_MAIN")
        main.init_app(app)

        cache = SanicRedis(config_name="REDIS_CACHE")
        cache.init_app(app, redis_url=redis_url)

        main_key = redis_key("main")
        cache_key = redis_key("cache")

        @app.get("/")
        async def handler(request):
            await request.app.ctx.redis_main.set(main_key, "main-value")
            await request.app.ctx.redis_cache.set(cache_key, "cache-value")
            main_value = await request.app.ctx.redis_main.get(main_key)
            cache_value = await request.app.ctx.redis_cache.get(cache_key)
            await request.app.ctx.redis_main.delete(main_key)
            await request.app.ctx.redis_cache.delete(cache_key)
            return json(
                {
                    "main_ping": await request.app.ctx.redis_main.ping(),
                    "cache_ping": await request.app.ctx.redis_cache.ping(),
                    "main_value": main_value.decode(),
                    "cache_value": cache_value.decode(),
                    "separate_clients": main.conn is not cache.conn,
                }
            )

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {
            "main_ping": True,
            "cache_ping": True,
            "main_value": "main-value",
            "cache_value": "cache-value",
            "separate_clients": True,
        }
