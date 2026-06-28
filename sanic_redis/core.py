"""
Sanic-Redis core file
"""

from typing import Optional

from redis.asyncio import client, from_url
from sanic import Sanic
from sanic.log import logger


class SanicRedis:
    """
    Redis Class for Sanic
    """

    conn: Optional[client.Redis]
    app: Optional[Sanic]
    redis_url: str
    config_name: str = "REDIS"
    single_connection_client: bool
    auto_close_connection_pool: Optional[bool]
    _connections: list[client.Redis]

    def __init__(
        self,
        app: Optional[Sanic] = None,
        config_name="REDIS",
        redis_url: str = "",
        single_connection_client: bool = False,
        auto_close_connection_pool: Optional[bool] = None,
    ):
        """
        init method of class
        """
        self.config_name = config_name
        self.redis_url = redis_url
        self.single_connection_client = single_connection_client
        self.auto_close_connection_pool = auto_close_connection_pool
        self.app = None
        self.conn = None
        self._connections = []
        if app:
            self.init_app(
                app=app,
                redis_url=redis_url,
                config_name=config_name,
                single_connection_client=single_connection_client,
                auto_close_connection_pool=auto_close_connection_pool,
            )

    def init_app(
        self,
        app: Sanic,
        config_name: Optional[str] = None,
        redis_url: Optional[str] = None,
        single_connection_client: Optional[bool] = None,
        auto_close_connection_pool: Optional[bool] = None,
    ):
        """
        init_app for Sanic
        """

        self.app = app
        if redis_url:
            self.redis_url = redis_url
        if config_name:
            self.config_name = config_name
        if single_connection_client is not None:
            self.single_connection_client = single_connection_client
        if auto_close_connection_pool is not None:
            self.auto_close_connection_pool = auto_close_connection_pool

        redis_url = self.redis_url
        config_name = self.config_name
        ctx_name = config_name.lower()
        single_connection_client = self.single_connection_client
        auto_close_connection_pool = self.auto_close_connection_pool
        redis_conn: Optional[client.Redis] = None

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
            from_url_kwargs = {
                "single_connection_client": single_connection_client,
            }
            if auto_close_connection_pool is not None:
                from_url_kwargs["auto_close_connection_pool"] = (
                    auto_close_connection_pool
                )
            _redis = from_url(_redis_url, **from_url_kwargs)
            setattr(_app.ctx, ctx_name, _redis)
            self._connections.append(_redis)
            redis_conn = _redis
            self.conn = _redis

        @app.listener("after_server_stop")
        async def close_redis(_app):
            nonlocal redis_conn
            logger.info("[sanic-redis] closing")
            _redis = redis_conn
            if _redis is not None:
                await _redis.aclose()
                redis_conn = None
                for index, active_conn in enumerate(self._connections):
                    if active_conn is _redis:
                        del self._connections[index]
                        break
                if self.conn is _redis:
                    self.conn = self._connections[-1] if self._connections else None
