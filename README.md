sanic-redis
==============
Redis support for sanic.

Built on top of [aioredis](https://github.com/aio-libs/aioredis).

Installation
------------

You can install this package as usual with pip:

    pip install sanic-redis

Example
------------

```python
from sanic import Sanic
from sanic.response import text
from sanic_redis import SanicRedis

app = Sanic(__name__)
app.config.update(
    {
        'REDIS': {
            'address': ('127.0.0.1', 6379),
            # 'db': 0,
            # 'password': 'password',
            # 'ssl': None,
            # 'encoding': None,
            # 'minsize': 1,
            # 'maxsize': 10
        }
    }
)


redis = SanicRedis(app)
#redis = SanicRedis()
#redis.init_app(app)
    
@app.route('/test1')
async def test1(request):
    with await redis.conn as r:
        await r.set('key', 'value1')
        result = await r.get('key')
    return text(result)


@app.route('/test2')
async def test2(request):
    with await request.app.redis as r:
        await r.set('key', 'value2')
        result = await r.get('key')
        return text(result)


if __name__ == '__main__':
    app.run(debug=True)
```

Create multiple aioredis instances
------------

```python
from sanic import Sanic
from sanic.response import text
from sanic_redis import SanicRedis


app = Sanic(__name__)


app.config.update({
    'REDIS_1': {
        'address': ('127.0.0.1', 6379),
        'db': 0,
    },
    'REDIS_2': {
        'address': ('127.0.0.1', 6379),
        'db': 1,
  }
})


r1 = SanicRedis(app, config_name="REDIS_1")
r2 = SanicRedis(app, config_name="REDIS_2")

#r1 = SanicRedis(config_name="REDIS_1")
#r2 = SanicRedis(config_name="REDIS_2")
#r1.init(app)
#r2.init(app)

@app.route('/test3')
async def test3(request):
    with await r1.conn as r:
        await r.set('key', 'value1')
    with await r2.conn as r:
            await r.set('key', 'value1')


@app.route('/test4')
async def test4(request):
    with await request.app.redis_1 as r:
        await r.set('key', 'value1')
    with await request.app.redis_2 as r:
        await r.set('key', 'value2')


if __name__ == '__main__':
    app.run(debug=True)
```

Resources
---------

- [PyPI](https://pypi.python.org/pypi/sanic-redis)
