sanic-redis
==============
Async Redis support for sanic.

Built on top of Async version of [Redis library](https://redis-py.readthedocs.io/en/stable/examples/asyncio_examples.html).

[HiRedis](https://github.com/redis/hiredis-py) is used by default for parsing the read results for a higher performance.

Installation
------------

You can install this package as usual with pip:

    pip install sanic-redis

Config
-----------
For example:
```
redis://[[username]:[password]]@localhost:6379/0
rediss://[[username]:[password]]@localhost:6379/0
unix://[username@]/path/to/socket.sock?db=0[&password=password]
```

Three URL schemes are supported:
  - `redis://` creates a TCP socket connection. See more at:
    <https://www.iana.org/assignments/uri-schemes/prov/redis>
  - `rediss://` creates a SSL wrapped TCP socket connection. See more at:
    <https://www.iana.org/assignments/uri-schemes/prov/rediss>
  - ``unix://``: creates a Unix Domain Socket connection.

Details: https://github.com/redis/redis-py/blob/1a7d474268fe7072686369adc20aa498d63f063e/redis/client.py#L103-L141

All allow querystring options:
```
{
    "db": int,
    "socket_timeout": float,
    "socket_connect_timeout": float,
    "socket_keepalive": bool,
    "retry_on_timeout": bool,
    "max_connections": int,
    "health_check_interval": int,
    "ssl_check_hostname": bool,
}
```
Details: https://github.com/redis/redis-py/blob/cc4bc1a544d1030aec1696baef2861064fa8dd1c/redis/asyncio/connection.py#L854-L864

Example
------------

```python
from sanic import Sanic
from sanic.response import text
from sanic_redis import SanicRedis

app = Sanic(__name__)

app.config.update(
    {
        'REDIS': "redis://localhost:6379/0",
        'REDIS1': "redis://localhost:6379/1",
        'REDIS2': "redis://localhost:6379/2",
    }
)

redis = SanicRedis() # default config_name is "REDIS"
redis.init_app(app)

redis1 = SanicRedis(config_name="REDIS1")
redis1.init_app(app)

redis2 = SanicRedis(config_name="REDIS2")
redis2.init_app(app)


@app.route('/test1')
async def test1(request):
    async with redis1.conn as r:
        await r.set("key1", "value1")
        result = await r.get("key1")
    return text(str(result))


@app.route('/test2')
async def test2(request):
    r = request.app.ctx.redis
    await r.set('key2', 'value2')
    result = await r.get('key2')
    return text(str(result))


@app.route('/test3')
async def test3(request):
    # request.app.ctx.{redis_name}, the {redis_name} == config_name.lower()
    async with request.app.ctx.redis1 as r:
        await r.set('key3', 'value3')
        result = await r.get('key3')
    return text(str(result))


if __name__ == '__main__':
    app.run(debug=True)

```

Resources
---------

- [PyPI](https://pypi.python.org/pypi/sanic-redis)
