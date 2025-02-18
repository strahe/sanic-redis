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

    conn: client.Redis
    app: Sanic
    redis_url: str
    config_name: str = "REDIS"
    single_connection_client: bool
    auto_close_connection_pool: Optional[bool]

    def __init__(self, app: Optional[Sanic] = None, config_name="REDIS",
                 redis_url: str = "",
                 single_connection_client: bool = False,
                 auto_close_connection_pool: Optional[bool] = None
                 ):
        """
            init method of class
        """
        self.config_name = config_name
        self.redis_url = redis_url
        self.single_connection_client = single_connection_client
        self.auto_close_connection_pool = auto_close_connection_pool
        if app:
            self.init_app(app=app,
                          redis_url=redis_url,
                          config_name=config_name,
                          single_connection_client=single_connection_client,
                          auto_close_connection_pool=auto_close_connection_pool)

    def init_app(self, app: Sanic, config_name: Optional[str] = None,
                 redis_url: Optional[str] = None,
                 single_connection_client: Optional[bool] = None,
                 auto_close_connection_pool: Optional[bool] = None):
        """
            init_app for Sanic
        """

        self.app = app
        if redis_url:
            self.redis_url = redis_url
        if config_name:
            self.config_name = config_name
        if single_connection_client:
            self.single_connection_client = single_connection_client
        if auto_close_connection_pool:
            self.auto_close_connection_pool = auto_close_connection_pool

        @app.listener('before_server_start')
        async def redis_configure(_app: Sanic, _loop):
            if self.redis_url:
                _redis_url = self.redis_url
            else:
                _redis_url = _app.config.get(self.config_name)
            if not _redis_url:
                raise ValueError(
                    f"You must specify a redis_url or set the "
                    f"{config_name} Sanic config variable"
                )
            logger.info("[sanic-redis] connecting")
            _redis = await from_url(_redis_url,
                                    single_connection_client=self.single_connection_client,
                                    auto_close_connection_pool=self.auto_close_connection_pool)
            setattr(_app.ctx, self.config_name.lower(), _redis)
            self.conn = _redis

        @app.listener('after_server_stop')
        async def close_redis(_app, _loop):
            logger.info("[sanic-redis] closing")
            await self.conn.aclose()
