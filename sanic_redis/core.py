import aioredis.client
from sanic import Sanic
from sanic.log import logger
from aioredis import from_url


class SanicRedis:

    conn: aioredis.client.Redis
    app: Sanic
    redis_url: str
    config_name: str

    def __init__(self, app: Sanic = None, config_name="REDIS", redis_url: str = ""):
        self.app: Sanic = app
        self.redis_url: str = redis_url
        self.conn: aioredis.client.Redis
        self.config_name: str = config_name

        if app:
            self.init_app(app=app)

    def init_app(self, app: Sanic, config_name: str = None, redis_url: str = ""):
        self.app = app
        self.redis_url = redis_url
        if config_name:
            self.config_name = config_name

        @app.listener('before_server_start')
        async def aio_redis_configure(_app: Sanic, _loop):
            if self.redis_url:
                _redis_url = self.redis_url
            else:
                _redis_url = _app.config.get(self.config_name)
            if not _redis_url:
                raise ValueError("You must specify a redis_url or set the {} Sanic config variable".format(config_name))
            logger.info("[sanic-redis] connecting")
            _redis = await from_url(_redis_url)
            setattr(_app.ctx, self.config_name.lower(), _redis)
            self.conn = _redis

        @app.listener('after_server_stop')
        async def close_redis(_app, _loop):
            logger.info("[sanic-redis] closing")
            await self.conn.close()
