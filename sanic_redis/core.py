"""
Sanic-Redis core file
"""

from typing import Any

from redis.asyncio import client, from_url
from sanic import Sanic
from sanic.log import logger


class SanicRedis:
    """
    Redis Class for Sanic
    """

    redis_url: str
    config_name: str = "REDIS"
    ctx_name: str | None
    single_connection_client: bool
    auto_close_connection_pool: bool | None
    from_url_kwargs: dict[str, Any]

    def __init__(
        self,
        app: Sanic | None = None,
        config_name: str = "REDIS",
        ctx_name: str | None = None,
        redis_url: str = "",
        single_connection_client: bool = False,
        auto_close_connection_pool: bool | None = None,
        from_url_kwargs: dict[str, Any] | None = None,
    ):
        """
        init method of class
        """
        self.config_name = config_name
        self.ctx_name = ctx_name
        self.redis_url = redis_url
        self.single_connection_client = single_connection_client
        self.auto_close_connection_pool = auto_close_connection_pool
        self.from_url_kwargs = dict(from_url_kwargs or {})
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
        from_url_kwargs: dict[str, Any] | None = None,
    ):
        """
        init_app for Sanic
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
        base_from_url_kwargs = (
            dict(self.from_url_kwargs)
            if from_url_kwargs is None
            else dict(from_url_kwargs)
        )
        redis_conn: client.Redis | None = None

        @app.listener("before_server_start")
        async def redis_configure(_app: Sanic):
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
            logger.info("[sanic-redis] connecting")
            redis_kwargs = dict(base_from_url_kwargs)
            redis_kwargs["single_connection_client"] = single_connection_client
            if auto_close_connection_pool is not None:
                redis_kwargs["auto_close_connection_pool"] = auto_close_connection_pool
            _redis = from_url(_redis_url, **redis_kwargs)
            setattr(_app.ctx, ctx_name, _redis)
            redis_conn = _redis

        @app.listener("after_server_stop")
        async def close_redis(_app):
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
