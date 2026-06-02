"""
Unit tests for Redis-based rate limiting (api.app.rate_limit).

Redis is mocked — no real Redis instance needed.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.app.auth import APIKeyRecord
from api.app.rate_limit import check_rate_limit


def make_record(plan: str = "dev") -> APIKeyRecord:
    return APIKeyRecord(
        id="test-id-1234",
        owner_name="Test Owner",
        owner_email="test@example.com",
        plan=plan,
        preview="tlm_1234...",
    )


def _make_request(ip: str = "1.2.3.4", forwarded_for: str | None = None):
    """Build a minimal mock FastAPI Request."""
    mock_request = MagicMock()
    mock_request.client.host = ip
    headers = {}
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    mock_request.headers.get = lambda key, default=None: headers.get(key, default)
    return mock_request


class TestRateLimitAnonymous:
    @pytest.mark.asyncio
    async def test_first_request_passes(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            # Should not raise
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_within_limit_passes(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 99
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_at_limit_passes(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 100
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 101
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await check_rate_limit(_make_request(), api_key=None)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_uses_forwarded_for_header(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        request = _make_request(ip="10.0.0.1", forwarded_for="203.0.113.5, 10.0.0.1")
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(request, api_key=None)
        # The Redis key should use the first IP in X-Forwarded-For
        call_args = mock_redis.incr.call_args[0][0]
        assert "203.0.113.5" in call_args


class TestRateLimitAuthenticated:
    @pytest.mark.asyncio
    async def test_dev_plan_higher_limit(self):
        """dev plan: 1 000 req/day — should pass at count 999."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 999
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=make_record(plan="dev"))

    @pytest.mark.asyncio
    async def test_dev_plan_over_limit_raises_429(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1001
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await check_rate_limit(_make_request(), api_key=make_record(plan="dev"))
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_institution_plan_very_high_limit(self):
        """institution plan: 100 000 req/day — pass at 99 999."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 99_999
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=make_record(plan="institution"))

    @pytest.mark.asyncio
    async def test_key_id_used_as_identifier_not_ip(self):
        """Rate limit bucket must use key ID, not the client IP."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        record = make_record()
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(ip="1.2.3.4"), api_key=record)
        redis_key = mock_redis.incr.call_args[0][0]
        assert record.id in redis_key
        assert "1.2.3.4" not in redis_key

    @pytest.mark.asyncio
    async def test_env_fallback_string_treated_as_dev(self):
        """String api_key (env fallback) → dev plan limits."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 999
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key="env-fallback-key")


class TestRateLimitFailOpen:
    @pytest.mark.asyncio
    async def test_redis_down_does_not_block_request(self):
        """If Redis is unavailable, the request must still pass (fail open)."""
        with patch("api.app.rate_limit._get_redis", side_effect=Exception("Redis down")):
            # Should NOT raise — fail open
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_redis_incr_error_does_not_block(self):
        mock_redis = MagicMock()
        mock_redis.incr.side_effect = Exception("INCR failed")
        with patch("api.app.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=None)
