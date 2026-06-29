sanic-redis
==============

[![Tests](https://github.com/strahe/sanic-redis/workflows/Tests/badge.svg)](https://github.com/strahe/sanic-redis/actions)
[![PyPI version](https://img.shields.io/pypi/v/sanic-redis.svg)](https://pypi.org/project/sanic-redis/)
[![Python versions](https://img.shields.io/pypi/pyversions/sanic-redis.svg)](https://pypi.org/project/sanic-redis/)

Async Redis support for Sanic.

Built on top of Async version of [Redis library](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html).

[HiRedis](https://github.com/redis/hiredis-py) is used by default for parsing the read results for a higher performance.

Installation
------------

You can install this package as usual with pip:

    pip install sanic-redis

Requires Python 3.10+, Sanic 25.3+, redis-py 7 or 8, and hiredis 3.2+.

Config
-----------

Redis URLs are passed to `redis.asyncio.from_url`. See the redis-py URL
documentation for supported schemes and query options:

<https://redis.readthedocs.io/en/stable/connections.html#redis.Redis.from_url>

Basic setup:

```python
app.config.REDIS = "redis://localhost:6379/0"
redis = SanicRedis()
redis.init_app(app)
```

Use `ctx_name` when the Sanic config key and runtime context name should differ:

```python
app.config.REDIS_CACHE = "redis://localhost:6379/1"
redis = SanicRedis(config_name="REDIS_CACHE", ctx_name="cache")
redis.init_app(app)
```

Pass redis-py client options with `from_url_kwargs`:

```python
redis = SanicRedis(from_url_kwargs={"decode_responses": True})
redis.init_app(app)
```

Use `single_connection_client` and `auto_close_connection_pool` as
`SanicRedis` parameters, not inside `from_url_kwargs`.

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

redis1 = SanicRedis(config_name="REDIS1", ctx_name="redis1")
redis1.init_app(app)

redis2 = SanicRedis(config_name="REDIS2", ctx_name="redis2")
redis2.init_app(app)


@app.route('/test1')
async def test1(request):
    r = request.app.ctx.redis1
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
    r = request.app.ctx.redis2
    await r.set('key3', 'value3')
    result = await r.get('key3')
    return text(str(result))


if __name__ == '__main__':
    app.run(debug=True)

```

Use `request.app.ctx.<name>` as the runtime connection source. `SanicRedis.conn`
and `SanicRedis.app` were removed in 0.7.

Testing
-------

```bash
pip install -e ".[test]"
docker compose -f docker-compose.test.yml up -d
tox -e py313-deps-latest
docker compose -f docker-compose.test.yml down
```

Run the quick compatibility smoke test with:

```bash
tox -e py313-deps-latest -- -m compat
```

Resources
---------

- [PyPI](https://pypi.python.org/pypi/sanic-redis)
