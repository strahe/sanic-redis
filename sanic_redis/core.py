from sanic import Sanic
from aioredis import create_redis_pool


class SanicRedis:
    def __init__(self, app: Sanic=None, config_name="REDIS", redis_config: dict=None):
        self.app = app
        self.config = redis_config
        self.conn = None
        self.config_name = config_name

        if app:
            self.init_app(app=app)

    def init_app(self, app: Sanic, config_name=None, redis_config: dict=None):
        self.app = app
        self.config = redis_config
        if config_name:
            self.config_name = config_name

        @app.listener('before_server_start')
        async def aio_redis_configure(_app, loop):
            _c = dict(loop=loop)
            if self.config:
                config = self.config
            else:
                config = _app.config.get(self.config_name)

            if not config:
                raise ValueError("You must specify a redis_config or set the REDIS Sanic config variable")
            if not isinstance(config, dict):
                raise TypeError("Redis Config must be a dict")
            for key in ['address', 'db', 'password', 'ssl', 'encoding', 'minsize',
                        'maxsize', 'timeout']:
                if key in config:
                    _c.update({key: config.get(key)})
            _redis = await create_redis_pool(**_c)
            setattr(_app, self.config_name.lower(), _redis)
            self.conn = _redis

        @app.listener('after_server_stop')
        async def close_redis(_app, _loop):
            self.conn.close()
            await self.conn.wait_closed()
