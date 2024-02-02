"""
Basic test for Sanic-Redis
Expects to have Redis on 127.0.0.1 with standard port
"""

import random
from sanic import Sanic
from sanic.response import text


def test_app_loop_running(app: Sanic):
    """
    Test uses random keys and values to verify the work of Redis with Sanic
    """
    test_key = f"test_key{random.random()}"
    test_value = f"{random.random()}_test_value"

    @app.get("/test")
    async def handler(request):
        redis = request.app.ctx.my_test_redis
        await redis.set(test_key, test_value)
        await redis.expire(test_key, 2)

        bytes_result = await redis.get(test_key)
        result = bytes_result.decode("utf-8")
        return text(result)

    _, response = app.test_client.get("/test")
    assert response.body == test_value.encode()
