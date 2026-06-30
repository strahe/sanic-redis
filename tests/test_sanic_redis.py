"""
Tests for the Sanic-Redis plugin behavior.
"""

from importlib.metadata import PackageNotFoundError, version

import pytest
from sanic import Sanic
from sanic.response import json

import sanic_redis.core as core
from sanic_redis import SanicRedis, __version__


class FakeRedis:
    def __init__(self, close_error=None, ping_error=None):
        self.closed = False
        self.pinged = False
        self.url = None
        self.close_error = close_error
        self.ping_error = ping_error

    async def ping(self):
        self.pinged = True
        if self.ping_error:
            raise self.ping_error
        return True

    async def aclose(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


class CloseError(BaseException):
    pass


def get_listener(app, event):
    return next(
        listener.listener
        for listener in app._future_listeners
        if listener.event == event
    )


def get_listeners(app, event):
    return [
        listener.listener
        for listener in app._future_listeners
        if listener.event == event
    ]


def major_minor(package):
    parts = version(package).split(".", 2)
    return int(parts[0]), int(parts[1])


def optional_major_minor(package):
    try:
        return major_minor(package)
    except PackageNotFoundError:
        return None


class TestSanicRedisUnit:
    def test_initializes_with_defaults_and_custom_values(self):
        redis = SanicRedis()

        assert redis.config_name == "REDIS"
        assert redis.ctx_name is None
        assert redis.redis_url == ""
        assert redis.single_connection_client is False
        assert redis.auto_close_connection_pool is None
        assert redis.from_url_kwargs == {}
        assert redis.ping_on_startup is False
        assert not hasattr(redis, "app")
        assert not hasattr(redis, "conn")

        custom = SanicRedis(
            config_name="CACHE",
            ctx_name="cache_client",
            redis_url="redis://example:6379/1",
            single_connection_client=True,
            auto_close_connection_pool=False,
            from_url_kwargs={"decode_responses": True},
            ping_on_startup=True,
        )

        assert custom.config_name == "CACHE"
        assert custom.ctx_name == "cache_client"
        assert custom.redis_url == "redis://example:6379/1"
        assert custom.single_connection_client is True
        assert custom.auto_close_connection_pool is False
        assert custom.from_url_kwargs == {"decode_responses": True}
        assert custom.ping_on_startup is True

    def test_init_app_does_not_mutate_default_configuration(self, app_name, redis_url):
        app = Sanic(app_name)
        redis = SanicRedis(
            config_name="ORIGINAL",
            ctx_name="original_client",
            redis_url="redis://original:6379/0",
            single_connection_client=True,
            auto_close_connection_pool=True,
            from_url_kwargs={"decode_responses": True},
            ping_on_startup=True,
        )

        redis.init_app(
            app,
            config_name="UPDATED",
            ctx_name="updated_client",
            redis_url=redis_url,
            single_connection_client=False,
            auto_close_connection_pool=False,
            from_url_kwargs={"encoding": "utf-8"},
            ping_on_startup=False,
        )

        assert redis.config_name == "ORIGINAL"
        assert redis.ctx_name == "original_client"
        assert redis.redis_url == "redis://original:6379/0"
        assert redis.single_connection_client is True
        assert redis.auto_close_connection_pool is True
        assert redis.from_url_kwargs == {"decode_responses": True}
        assert redis.ping_on_startup is True

    @pytest.mark.parametrize(
        ("option_name", "expected_name"),
        (
            ("auto_close_connection_pool", "auto_close_connection_pool"),
            ("Auto_Close_Connection_Pool", "auto_close_connection_pool"),
            ("single_connection_client", "single_connection_client"),
            ("Single_Connection_Client", "single_connection_client"),
        ),
    )
    def test_from_url_kwargs_rejects_plugin_parameters(
        self, app_name, option_name, expected_name
    ):
        with pytest.raises(ValueError, match=expected_name):
            SanicRedis(from_url_kwargs={option_name: True})

        app = Sanic(app_name)
        redis = SanicRedis()

        with pytest.raises(ValueError, match=expected_name):
            redis.init_app(app, from_url_kwargs={option_name: True})

    @pytest.mark.parametrize(
        ("option_name", "expected_name"),
        (
            ("auto_close_connection_pool", "auto_close_connection_pool"),
            ("Auto_Close_Connection_Pool", "auto_close_connection_pool"),
            ("single_connection_client", "single_connection_client"),
            ("Single_Connection_Client", "single_connection_client"),
        ),
    )
    def test_explicit_redis_url_rejects_plugin_query_parameters(
        self, app_name, option_name, expected_name
    ):
        app = Sanic(app_name)
        redis = SanicRedis()

        with pytest.raises(ValueError, match=expected_name):
            redis.init_app(
                app,
                redis_url=f"redis://localhost:6379/0?{option_name}=True",
            )

    def test_package_exports_public_objects(self):
        assert SanicRedis is not None
        assert callable(SanicRedis)
        assert isinstance(__version__, str)
        assert __version__

        redis = SanicRedis()
        for attr in (
            "config_name",
            "ctx_name",
            "redis_url",
            "single_connection_client",
            "auto_close_connection_pool",
            "from_url_kwargs",
            "ping_on_startup",
            "init_app",
        ):
            assert hasattr(redis, attr)


class TestSanicRedisStartup:
    @pytest.mark.asyncio
    async def test_startup_uses_config_url_and_closes_ctx_client(
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
        SanicRedis(app=app, config_name="REDIS_CACHE", single_connection_client=True)

        @app.get("/")
        async def handler(request):
            return json({"ctx_has_client": request.app.ctx.redis_cache is fake})

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {"ctx_has_client": True}
        assert calls == [
            (
                "redis://config:6379/1",
                {"single_connection_client": True},
            )
        ]
        assert fake.pinged is False
        assert fake.closed is True
        assert not hasattr(app.ctx, "redis_cache")

    @pytest.mark.asyncio
    async def test_startup_uses_init_app_options_and_from_url_kwargs(
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
        redis = SanicRedis(
            single_connection_client=True,
            from_url_kwargs={"decode_responses": True},
        )
        redis.init_app(
            app,
            ctx_name="cache",
            redis_url=redis_url,
            single_connection_client=False,
            auto_close_connection_pool=False,
            from_url_kwargs={"encoding": "utf-8"},
        )

        @app.get("/")
        async def handler(request):
            return json({"ctx_has_client": request.app.ctx.cache is fake})

        _, response = await app.asgi_client.get("/")

        assert response.status_code == 200
        assert response.json == {"ctx_has_client": True}
        assert calls == [
            (
                redis_url,
                {
                    "encoding": "utf-8",
                    "single_connection_client": False,
                    "auto_close_connection_pool": False,
                },
            )
        ]
        assert redis.from_url_kwargs == {"decode_responses": True}

    @pytest.mark.asyncio
    async def test_startup_ping_on_startup_checks_client_before_ctx(
        self, app_name, redis_url, monkeypatch
    ):
        fake = FakeRedis()
        calls = []

        def fake_from_url(url, **kwargs):
            calls.append((url, kwargs))
            return fake

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        redis = SanicRedis(ping_on_startup=True)
        redis.init_app(app, redis_url=redis_url)

        await get_listener(app, "before_server_start")(app)

        assert calls == [(redis_url, {"single_connection_client": False})]
        assert fake.pinged is True
        assert app.ctx.redis is fake

        await get_listener(app, "after_server_stop")(app)

    @pytest.mark.asyncio
    async def test_startup_ping_failure_closes_client_and_preserves_exception(
        self, app_name, redis_url, monkeypatch
    ):
        fake = FakeRedis(
            close_error=CloseError("close failed"),
            ping_error=RuntimeError("ping failed"),
        )

        def fake_from_url(url, **kwargs):
            return fake

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        redis = SanicRedis(ping_on_startup=True)
        redis.init_app(app, redis_url=redis_url)

        with pytest.raises(RuntimeError, match="ping failed"):
            await get_listener(app, "before_server_start")(app)

        assert fake.pinged is True
        assert fake.closed is True
        assert not hasattr(app.ctx, "redis")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("default_ping", "override_ping", "expected_ping"),
        (
            (False, True, True),
            (True, False, False),
        ),
    )
    async def test_init_app_ping_on_startup_overrides_default(
        self,
        app_name,
        redis_url,
        monkeypatch,
        default_ping,
        override_ping,
        expected_ping,
    ):
        fake = FakeRedis()

        def fake_from_url(url, **kwargs):
            return fake

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        redis = SanicRedis(ping_on_startup=default_ping)
        redis.init_app(app, redis_url=redis_url, ping_on_startup=override_ping)

        await get_listener(app, "before_server_start")(app)

        assert fake.pinged is expected_ping
        assert app.ctx.redis is fake

        await get_listener(app, "after_server_stop")(app)

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
    @pytest.mark.parametrize(
        ("option_name", "expected_name"),
        (
            ("auto_close_connection_pool", "auto_close_connection_pool"),
            ("Auto_Close_Connection_Pool", "auto_close_connection_pool"),
            ("single_connection_client", "single_connection_client"),
            ("Single_Connection_Client", "single_connection_client"),
        ),
    )
    async def test_config_redis_url_rejects_plugin_query_parameters_before_from_url(
        self, app_name, monkeypatch, option_name, expected_name
    ):
        calls = []

        def fake_from_url(url, **kwargs):
            calls.append((url, kwargs))
            return FakeRedis()

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        app.config.REDIS = f"redis://localhost:6379/0?{option_name}=True"
        redis = SanicRedis()
        redis.init_app(app)

        with pytest.raises(ValueError, match=expected_name):
            await get_listener(app, "before_server_start")(app)

        assert calls == []

    @pytest.mark.asyncio
    async def test_reused_extension_keeps_app_options_and_clients_isolated(
        self, app_name, monkeypatch
    ):
        clients = []

        def fake_from_url(url, **kwargs):
            client = FakeRedis()
            client.url = url
            clients.append(client)
            return client

        monkeypatch.setattr(core, "from_url", fake_from_url)

        redis = SanicRedis(config_name="DEFAULT", redis_url="redis://default:6379/0")
        first_app = Sanic(f"{app_name}-first")
        second_app = Sanic(f"{app_name}-second")
        third_app = Sanic(f"{app_name}-third")

        redis.init_app(
            first_app,
            config_name="FIRST",
            ctx_name="first_client",
            redis_url="redis://first:6379/0",
        )
        redis.init_app(
            second_app,
            config_name="SECOND",
            ctx_name="second_client",
            redis_url="redis://second:6379/0",
        )
        redis.init_app(third_app, ctx_name="third_client")

        await get_listener(first_app, "before_server_start")(first_app)
        await get_listener(second_app, "before_server_start")(second_app)
        await get_listener(third_app, "before_server_start")(third_app)

        first_client = first_app.ctx.first_client
        second_client = second_app.ctx.second_client
        third_client = third_app.ctx.third_client

        assert [client.url for client in clients] == [
            "redis://first:6379/0",
            "redis://second:6379/0",
            "redis://default:6379/0",
        ]

        await get_listener(second_app, "after_server_stop")(second_app)

        assert first_client.closed is False
        assert second_client.closed is True
        assert third_client.closed is False
        assert hasattr(first_app.ctx, "first_client")
        assert not hasattr(second_app.ctx, "second_client")
        assert hasattr(third_app.ctx, "third_client")

        await get_listener(third_app, "after_server_stop")(third_app)
        await get_listener(first_app, "after_server_stop")(first_app)

        assert first_client.closed is True
        assert third_client.closed is True
        assert not hasattr(first_app.ctx, "first_client")
        assert not hasattr(third_app.ctx, "third_client")

    @pytest.mark.asyncio
    async def test_repeated_init_app_keeps_latest_ctx_client_until_its_listener_stops(
        self, app_name, monkeypatch
    ):
        clients = []

        def fake_from_url(url, **kwargs):
            client = FakeRedis()
            client.url = url
            clients.append(client)
            return client

        monkeypatch.setattr(core, "from_url", fake_from_url)

        app = Sanic(app_name)
        redis = SanicRedis()
        redis.init_app(app, redis_url="redis://first:6379/0")
        redis.init_app(app, redis_url="redis://second:6379/0")

        start_listeners = get_listeners(app, "before_server_start")
        stop_listeners = get_listeners(app, "after_server_stop")

        for start in start_listeners:
            await start(app)

        assert [client.url for client in clients] == [
            "redis://first:6379/0",
            "redis://second:6379/0",
        ]
        assert app.ctx.redis is clients[1]

        await stop_listeners[0](app)

        assert clients[0].closed is True
        assert clients[1].closed is False
        assert app.ctx.redis is clients[1]

        await stop_listeners[1](app)

        assert clients[1].closed is True
        assert not hasattr(app.ctx, "redis")

    @pytest.mark.asyncio
    async def test_close_error_cleans_ctx_and_preserves_exception(
        self, app_name, monkeypatch
    ):
        clients = []

        def fake_from_url(url, **kwargs):
            close_error = RuntimeError("close failed") if "second" in url else None
            client = FakeRedis(close_error=close_error)
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

        with pytest.raises(RuntimeError, match="close failed"):
            await get_listener(second_app, "after_server_stop")(second_app)

        assert first_client.closed is False
        assert second_client.closed is True
        assert hasattr(first_app.ctx, "redis")
        assert not hasattr(second_app.ctx, "redis")

        await get_listener(first_app, "after_server_stop")(first_app)

        assert first_client.closed is True
        assert not hasattr(first_app.ctx, "redis")


class TestSanicRedisIntegration:
    @pytest.mark.asyncio
    @pytest.mark.compat
    @pytest.mark.integration
    async def test_compatibility_smoke(self, app_name, redis_url, redis_key):
        assert major_minor("sanic") >= (25, 3)
        assert version("redis").split(".", 1)[0] in {"7", "8"}
        hiredis_version = optional_major_minor("hiredis")
        if hiredis_version is not None:
            assert (3, 2) <= hiredis_version < (4, 0)
        assert callable(core.from_url)

        app = Sanic(app_name)
        redis = SanicRedis(ping_on_startup=True)
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
                    "ctx_has_client": hasattr(request.app.ctx, "redis"),
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
            main_client = request.app.ctx.redis_main
            cache_client = request.app.ctx.redis_cache
            await main_client.set(main_key, "main-value")
            await cache_client.set(cache_key, "cache-value")
            main_value = await main_client.get(main_key)
            cache_value = await cache_client.get(cache_key)
            await main_client.delete(main_key)
            await cache_client.delete(cache_key)
            return json(
                {
                    "main_ping": await main_client.ping(),
                    "cache_ping": await cache_client.ping(),
                    "main_value": main_value.decode(),
                    "cache_value": cache_value.decode(),
                    "separate_clients": main_client is not cache_client,
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
