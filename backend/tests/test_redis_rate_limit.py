import asyncio
import hashlib
import os
import socket
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as redis
from fastapi import HTTPException, Request

from app.core.config import settings
from app.main import app
from app.services.rate_limit_service import enforce_rate_limit


REDIS_TEST_URL = os.environ.get("NSS_REDIS_TEST_URL")
pytestmark = pytest.mark.skipif(
    not REDIS_TEST_URL,
    reason="Set NSS_REDIS_TEST_URL to an isolated disposable Redis instance.",
)


@pytest.fixture
def redis_context():
    if not REDIS_TEST_URL:
        pytest.skip("An isolated Redis test URL was not configured.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = redis.Redis.from_url(
        REDIS_TEST_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    previous_redis = getattr(app.state, "redis", None)
    app.state.redis = client
    try:
        loop.run_until_complete(client.ping())
        yield client, loop
    finally:
        app.state.redis = previous_redis
        loop.run_until_complete(client.aclose())
        loop.close()
        asyncio.set_event_loop(None)


def _identity_key(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _service_key(scope: str, identity: str) -> str:
    return f"nss-bloodconnect:rate-limit:{scope}:{_identity_key(identity)}"


def _request(client_host: str) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/rate-limit-test",
        "raw_path": b"/rate-limit-test",
        "query_string": b"",
        "headers": [],
        "client": (client_host, 12345),
        "server": ("localhost", 8000),
        "app": app,
    })


async def _parallel_http(client_host: str, requests):
    transport = httpx.ASGITransport(app=app, client=(client_host, 12345))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await asyncio.gather(*(
            client.request(method, path, json=payload)
            for method, path, payload in requests
        ))


def test_real_redis_concurrent_threshold_is_atomic_and_keys_are_isolated(redis_context):
    client, loop = redis_context
    identity = f"synthetic-concurrency:{uuid4().hex}"
    second_identity = f"synthetic-independent:{uuid4().hex}"
    scope = f"redis-test-{uuid4().hex}"
    key = _service_key(scope, identity)
    second_key = _service_key(scope, second_identity)

    async def call(identity_value):
        await enforce_rate_limit(
            _request("198.51.100.21"),
            scope=scope,
            maximum=13,
            window_seconds=30,
            identity=identity_value,
        )

    async def run_test():
        results = await asyncio.gather(
            *(call(identity) for _ in range(80)),
            return_exceptions=True,
        )
        allowed = [result for result in results if not isinstance(result, BaseException)]
        rejected = [result for result in results if isinstance(result, HTTPException)]
        unexpected = [
            result for result in results
            if isinstance(result, BaseException) and not isinstance(result, HTTPException)
        ]
        assert not unexpected
        assert len(allowed) == 13
        assert len(rejected) == 67
        assert all(result.status_code == 429 for result in rejected)
        assert all(result.headers.get("Retry-After") for result in rejected)
        assert await client.get(key) == "80"
        assert 0 < await client.pttl(key) <= 30_000

        await call(second_identity)
        assert await client.get(second_key) == "1"

    try:
        loop.run_until_complete(run_test())
    finally:
        loop.run_until_complete(client.delete(key, second_key))


def test_real_redis_window_expires_and_resets(redis_context):
    client, loop = redis_context
    identity = f"synthetic-expiry:{uuid4().hex}"
    scope = f"redis-expiry-{uuid4().hex}"
    key = _service_key(scope, identity)
    request = _request("198.51.100.22")

    async def call():
        await enforce_rate_limit(
            request,
            scope=scope,
            maximum=1,
            window_seconds=1,
            identity=identity,
        )

    async def run_test():
        await call()
        with pytest.raises(HTTPException) as limited:
            await call()
        assert limited.value.status_code == 429
        ttl = await client.pttl(key)
        assert 0 < ttl <= 1000
        await asyncio.sleep(1.2)
        await call()
        assert await client.get(key) == "1"

    try:
        loop.run_until_complete(run_test())
    finally:
        loop.run_until_complete(client.delete(key))


def test_concurrent_login_requests_enforce_real_redis_threshold(redis_context):
    client, loop = redis_context
    client_host = f"redis-login-{uuid4().hex}"
    key = _service_key("login", f"ip:{client_host}")
    request = ("POST", "/api/auth/login", {
        "email": "missing-redis-test@example.org",
        "password": "NotARealPassword123",
    })
    try:
        responses = loop.run_until_complete(
            _parallel_http(client_host, [request] * 18)
        )
        assert sum(response.status_code == 401 for response in responses) == 5
        limited = [response for response in responses if response.status_code == 429]
        assert len(limited) == 13
        assert all(response.headers.get("Retry-After") for response in limited)
        assert loop.run_until_complete(client.get(key)) == "18"
    finally:
        loop.run_until_complete(client.delete(key))


def test_concurrent_registration_requests_enforce_real_redis_threshold(redis_context):
    client, loop = redis_context
    client_host = f"redis-registration-{uuid4().hex}"
    key = _service_key("registration", f"ip:{client_host}")
    requests = [
        ("POST", "/api/auth/register", {
            "full_name": "Synthetic Redis Registration",
            "email": f"redis-registration-{uuid4().hex}-{index}@example.org",
            "phone": "9876543210",
            "password": "SyntheticSafePassword123",
            "role": "requester",
        })
        for index in range(12)
    ]
    try:
        responses = loop.run_until_complete(_parallel_http(client_host, requests))
        assert sum(response.status_code == 201 for response in responses) == 5, [
            response.status_code for response in responses
        ]
        limited = [response for response in responses if response.status_code == 429]
        assert len(limited) == 7, [response.status_code for response in responses]
        assert all(response.headers.get("Retry-After") for response in limited)
        assert loop.run_until_complete(client.get(key)) == "12"
    finally:
        loop.run_until_complete(client.delete(key))


def test_concurrent_password_reset_requests_enforce_real_redis_threshold(redis_context):
    client, loop = redis_context
    client_host = f"redis-reset-{uuid4().hex}"
    key = _service_key("password-reset", f"ip:{client_host}")
    requests = [
        ("POST", "/api/auth/forgot-password", {
            "email": f"missing-{uuid4().hex}@example.org",
        })
        for _ in range(12)
    ]
    try:
        responses = loop.run_until_complete(_parallel_http(client_host, requests))
        assert sum(response.status_code == 200 for response in responses) == 3
        limited = [response for response in responses if response.status_code == 429]
        assert len(limited) == 9
        assert all(response.headers.get("Retry-After") for response in limited)
        assert loop.run_until_complete(client.get(key)) == "12"
    finally:
        loop.run_until_complete(client.delete(key))


def test_concurrent_password_reset_completions_enforce_real_redis_threshold(
    redis_context,
):
    client, loop = redis_context
    client_host = f"redis-reset-complete-{uuid4().hex}"
    key = _service_key("password-reset", f"ip:{client_host}")
    requests = [
        ("POST", "/api/auth/reset-password", {
            "token": f"synthetic-invalid-reset-token-{uuid4().hex}",
            "new_password": "SyntheticSafePassword123",
        })
        for _ in range(8)
    ]
    try:
        responses = loop.run_until_complete(_parallel_http(client_host, requests))
        assert sum(response.status_code == 400 for response in responses) == 3
        limited = [response for response in responses if response.status_code == 429]
        assert len(limited) == 5
        assert all(response.headers.get("Retry-After") for response in limited)
        assert loop.run_until_complete(client.get(key)) == "8"
    finally:
        loop.run_until_complete(client.delete(key))


def test_real_redis_outage_fails_closed_in_production_and_recovers(
    redis_context,
    monkeypatch,
):
    live_client, loop = redis_context
    client_host = f"redis-outage-{uuid4().hex}"
    key = _service_key("login", f"ip:{client_host}")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        unavailable_port = probe.getsockname()[1]

    dead_client = redis.Redis.from_url(
        f"redis://127.0.0.1:{unavailable_port}/15",
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
        retry_on_timeout=False,
    )
    previous_redis = app.state.redis
    app.state.redis = dead_client
    monkeypatch.setattr(settings, "app_env", "production")
    request = ("POST", "/api/auth/login", {
        "email": "missing-redis-test@example.org",
        "password": "NotARealPassword123",
    })
    try:
        failed = loop.run_until_complete(
            _parallel_http(client_host, [request])
        )[0]
        assert failed.status_code == 503

        app.state.redis = live_client
        recovered = loop.run_until_complete(
            _parallel_http(client_host, [request])
        )[0]
        assert recovered.status_code == 401
        assert loop.run_until_complete(live_client.get(key)) == "1"
    finally:
        app.state.redis = previous_redis
        loop.run_until_complete(dead_client.aclose())
        loop.run_until_complete(live_client.delete(key))
