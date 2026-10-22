import hashlib
import logging
import math

from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

_INCREMENT_WITH_EXPIRY = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('PTTL', KEYS[1])}
"""


async def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    maximum: int,
    window_seconds: int,
    identity: str | None = None,
) -> None:
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        if settings.app_env.strip().lower() in {"production", "staging"}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting is temporarily unavailable.",
            )
        return

    client_ip = request.client.host if request.client else "unknown"
    rate_identity = identity or f"ip:{client_ip}"
    identity_key = hashlib.sha256(rate_identity.encode("utf-8")).hexdigest()
    key = f"nss-bloodconnect:rate-limit:{scope}:{identity_key}"
    try:
        count, ttl_milliseconds = await redis_client.eval(
            _INCREMENT_WITH_EXPIRY,
            1,
            key,
            window_seconds * 1000,
        )
    except RedisError:
        logger.warning("Rate-limit store request failed for scope %s.", scope)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting is temporarily unavailable.",
        ) from None

    if int(count) > maximum:
        retry_after = max(1, math.ceil(int(ttl_milliseconds) / 1000))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


async def limit_login(request: Request) -> None:
    await enforce_rate_limit(request, scope="login", maximum=5, window_seconds=15 * 60)


async def limit_registration(request: Request) -> None:
    await enforce_rate_limit(request, scope="registration", maximum=5, window_seconds=60 * 60)


async def limit_password_reset(request: Request) -> None:
    await enforce_rate_limit(request, scope="password-reset", maximum=3, window_seconds=60 * 60)


async def limit_ai_chat(
    request: Request,
    user: User = Depends(get_current_active_user),
) -> None:
    await enforce_rate_limit(request, scope="ai-chat", maximum=20, window_seconds=60, identity=f"user:{user.id}")


async def limit_matching(
    request: Request,
    user: User = Depends(get_current_active_user),
) -> None:
    await enforce_rate_limit(request, scope="matching", maximum=30, window_seconds=60, identity=f"user:{user.id}")
