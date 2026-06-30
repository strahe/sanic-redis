"""
Sanic-Redis core file
"""

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from redis.asyncio import Redis, from_url
from sanic import Sanic
from sanic.log import logger

PLUGIN_FROM_URL_KWARGS = {"auto_close_connection_pool", "single_connection_client"}


def _reject_plugin_options(option_names: Iterable[str], source: str) -> None:
    conflicts = {
        option_name.lower()
        for option_name in option_names
        if option_name.lower() in PLUGIN_FROM_URL_KWARGS
    }
    if not conflicts:
        return
    names = ", ".join(sorted(conflicts))
    raise ValueError(
        f"Use SanicRedis parameters for {names}; do not pass them in {source}"
    )


def _copy_from_url_kwargs(
    from_url_kwargs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    copied = dict(from_url_kwargs or {})
    _reject_plugin_options(copied.keys(), "from_url_kwargs")
    return copied


def _validate_redis_url(redis_url: str) -> None:
    query_options = (
        name
        for name, _value in parse_qsl(urlsplit(redis_url).query, keep_blank_values=True)
    )
    _reject_plugin_options(query_options, "Redis URL query")


class SanicRedis:
    """
    Register redis.asyncio clients on a Sanic app lifecycle.
    """

    redis_url: str
    config_name: str = "REDIS"
    ctx_name: str | None
    single_connection_client: bool
    auto_close_connection_pool: bool | None
    from_url_kwargs: dict[str, Any]
    ping_on_startup: bool

    def __init__(
        self,
        app: Sanic | None = None,
        config_name: str = "REDIS",
        ctx_name: str | None = None,
        redis_url: str = "",
        single_connection_client: bool = False,
        auto_close_connection_pool: bool | None = None,
        from_url_kwargs: Mapping[str, Any] | None = None,
        ping_on_startup: bool = False,
    ) -> None:
        """
        Store default Redis options and optionally bind them to an app.
        """
        self.config_name = config_name
        self.ctx_name = ctx_name
        self.redis_url = redis_url
        self.single_connection_client = single_connection_client
        self.auto_close_connection_pool = auto_close_connection_pool
        self.from_url_kwargs = _copy_from_url_kwargs(from_url_kwargs)
        self.ping_on_startup = ping_on_startup
        if app is not None:
            self.init_app(app)

    def init_app(
        self,
        app: Sanic,
        config_name: str | None = None,
        ctx_name: str | None = None,
        redis_url: str | None = None,
        single_connection_client: bool | None = None,
        auto_close_connection_pool: bool | None = None,
        from_url_kwargs: Mapping[str, Any] | None = None,
        ping_on_startup: bool | None = None,
    ) -> None:
        """
        Register Redis startup and shutdown listeners on a Sanic app.
        """

        redis_url = self.redis_url if redis_url is None else redis_url
        config_name = self.config_name if config_name is None else config_name
        ctx_name = self.ctx_name if ctx_name is None else ctx_name
        ctx_name = ctx_name or config_name.lower()
        single_connection_client = (
            self.single_connection_client
            if single_connection_client is None
            else single_connection_client
        )
        auto_close_connection_pool = (
            self.auto_close_connection_pool
            if auto_close_connection_pool is None
            else auto_close_connection_pool
        )
        ping_on_startup = (
            self.ping_on_startup if ping_on_startup is None else ping_on_startup
        )
        base_from_url_kwargs = (
            dict(self.from_url_kwargs)
            if from_url_kwargs is None
            else _copy_from_url_kwargs(from_url_kwargs)
        )
        if redis_url:
            _validate_redis_url(redis_url)
        redis_conn: Redis | None = None

        @app.listener("before_server_start")
        async def redis_configure(_app: Sanic) -> None:
            nonlocal redis_conn
            if redis_url:
                _redis_url = redis_url
            else:
                _redis_url = _app.config.get(config_name)
                if not _redis_url:
                    raise ValueError(
                        f"You must specify a redis_url or set the "
                        f"{config_name} Sanic config variable"
                    )
                _validate_redis_url(_redis_url)
            logger.info("[sanic-redis] connecting")
            redis_kwargs = dict(base_from_url_kwargs)
            redis_kwargs["single_connection_client"] = single_connection_client
            if auto_close_connection_pool is not None:
                redis_kwargs["auto_close_connection_pool"] = auto_close_connection_pool
            _redis = from_url(_redis_url, **redis_kwargs)
            if ping_on_startup:
                try:
                    await _redis.ping()
                except BaseException:
                    try:
                        await _redis.aclose()
                    except Exception:
                        logger.warning(
                            "[sanic-redis] failed to close Redis client after "
                            "startup ping failure",
                            exc_info=True,
                        )
                    raise
            setattr(_app.ctx, ctx_name, _redis)
            redis_conn = _redis

        @app.listener("after_server_stop")
        async def close_redis(_app: Sanic) -> None:
            nonlocal redis_conn
            logger.info("[sanic-redis] closing")
            _redis = redis_conn
            if _redis is not None:
                try:
                    await _redis.aclose()
                finally:
                    redis_conn = None
                    if getattr(_app.ctx, ctx_name, None) is _redis:
                        delattr(_app.ctx, ctx_name)
