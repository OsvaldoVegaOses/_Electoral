import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

redis = pytest.importorskip("redis")

from app.rate_limiter import _redis_check


@pytest.fixture
def redis_clients():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        if os.getenv("REQUIRE_S2_SERVICES") == "1":
            pytest.fail("REDIS_URL es obligatorio en integración")
        pytest.skip("REDIS_URL no está configurado")

    clients = [
        redis.Redis.from_url(redis_url, decode_responses=True),
        redis.Redis.from_url(redis_url, decode_responses=True),
    ]
    try:
        for client in clients:
            client.ping()
    except redis.RedisError as exc:
        if os.getenv("REQUIRE_S2_SERVICES") == "1":
            pytest.fail("Redis obligatorio no disponible", pytrace=False)
        pytest.skip(f"Redis de prueba no está disponible: {exc}")

    yield clients

    for client in clients:
        client.close()


def test_two_redis_clients_count_concurrent_requests_atomically(redis_clients):
    ip = f"s2-e-{uuid.uuid4()}"
    with ThreadPoolExecutor(max_workers=20) as pool:
        counts = list(
            pool.map(
                lambda index: _redis_check(
                    redis_clients[index % len(redis_clients)], ip, 60, 100
                ),
                range(100),
            )
        )

    assert sorted(counts) == list(range(1, 101))
    assert redis_clients[0].zcard(f"rl:{ip}") == 100
    redis_clients[0].delete(f"rl:{ip}")


def test_redis_sliding_window_expires_old_attempts(redis_clients):
    ip = f"s2-e-expiry-{uuid.uuid4()}"
    first_count = _redis_check(redis_clients[0], ip, 1, 10)
    assert first_count == 1

    time.sleep(1.1)

    assert _redis_check(redis_clients[1], ip, 1, 10) == 1
    redis_clients[0].delete(f"rl:{ip}")
