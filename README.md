sanic-redis
==============
Redis support for sanic.

Built on top of [aioredis](https://github.com/aio-libs/aioredis).

Installation
------------

You can install this package as usual with pip:

    pip install sanic-redis

Example

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
    
    
@app.route('/test1')
async def test1(request):
    with await redis.acquire() as r:
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

Resources
---------

- [PyPI](https://pypi.python.org/pypi/sanic-redis)
