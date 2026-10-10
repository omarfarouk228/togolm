"""
Unit tests for Redis-based rate limiting (api.app.rate_limit).

Redis is mocked — no real Redis instance needed.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from api.app.core.auth import APIKeyRecord
from api.app.core.rate_limit import check_rate_limit


def make_record(plan: str = "dev") -> APIKeyRecord:
    return APIKeyRecord(
        id="test-id-1234",
        owner_name="Test Owner",
        owner_email="test@example.com",
        plan=plan,
        preview="tlm_1234...",
    )


def _make_request(
    ip: str = "1.2.3.4", forwarded_for: str | None = None, real_ip: str | None = None
):
    """Build a minimal mock FastAPI Request."""
    mock_request = MagicMock()
    mock_request.client.host = ip
    headers = {}
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    if real_ip:
        headers["X-Real-IP"] = real_ip
    mock_request.headers.get = lambda key, default=None: headers.get(key, default)
    return mock_request


class TestRateLimitAnonymous:
    @pytest.mark.asyncio
    async def test_first_request_passes(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            # Should not raise
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_within_limit_passes(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 10  # within anon limit of 20
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_at_limit_passes(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = (
            20  # exactly at anon limit; count > max_req → 20 > 20 = False
        )
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 101
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await check_rate_limit(_make_request(), api_key=None)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_uses_forwarded_for_header(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        request = _make_request(ip="10.0.0.1", forwarded_for="203.0.113.5, 10.0.0.1")
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(request, api_key=None)
        # Fallback (no X-Real-IP): use the leftmost X-Forwarded-For entry (original client)
        call_args = mock_redis.incr.call_args[0][0]
        assert "203.0.113.5" in call_args

    @pytest.mark.asyncio
    async def test_real_ip_header_takes_priority_over_forwarded_for(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        # X-Real-IP is set by Nginx from $remote_addr — it cannot be forged by the client
        request = _make_request(
            ip="10.0.0.1",
            forwarded_for="spoofed_ip, 10.0.0.1",
            real_ip="203.0.113.5",
        )
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(request, api_key=None)
        call_args = mock_redis.incr.call_args[0][0]
        assert "203.0.113.5" in call_args
        assert "spoofed_ip" not in call_args


class TestRateLimitAuthenticated:
    @pytest.mark.asyncio
    async def test_dev_plan_higher_limit(self):
        """dev plan: 1 000 req/day — should pass at count 999."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 999
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=make_record(plan="dev"))

    @pytest.mark.asyncio
    async def test_dev_plan_over_limit_raises_429(self):
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1001
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await check_rate_limit(_make_request(), api_key=make_record(plan="dev"))
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_institution_plan_very_high_limit(self):
        """institution plan: 100 000 req/day — pass at 99 999."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 99_999
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=make_record(plan="institution"))

    @pytest.mark.asyncio
    async def test_key_id_used_as_identifier_not_ip(self):
        """Rate limit bucket must use key ID, not the client IP."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        record = make_record()
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(ip="1.2.3.4"), api_key=record)
        redis_key = mock_redis.incr.call_args[0][0]
        assert record.id in redis_key
        assert "1.2.3.4" not in redis_key

    @pytest.mark.asyncio
    async def test_env_fallback_string_treated_as_dev(self):
        """String api_key (env fallback) → dev plan limits."""
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 999
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key="env-fallback-key")


class TestRateLimitFailOpen:
    @pytest.mark.asyncio
    async def test_redis_down_does_not_block_request(self):
        """If Redis is unavailable, the request must still pass (fail open)."""
        with patch("api.app.core.rate_limit._get_redis", side_effect=Exception("Redis down")):
            # Should NOT raise — fail open
            await check_rate_limit(_make_request(), api_key=None)

    @pytest.mark.asyncio
    async def test_redis_incr_error_does_not_block(self):
        mock_redis = MagicMock()
        mock_redis.incr.side_effect = Exception("INCR failed")
        with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
            await check_rate_limit(_make_request(), api_key=None)


class TestRateLimitPerDevice:
    """Anonymous quota per device (X-Client-Id) under a shared per-IP ceiling."""

    @staticmethod
    def _request(client_id: str | None, ip: str = "41.207.1.1"):
        headers = {"X-Real-IP": ip}
        if client_id is not None:
            headers["X-Client-Id"] = client_id
        req = MagicMock()
        req.client.host = ip
        req.headers.get = lambda key, default=None: headers.get(key, default)
        return req

    @staticmethod
    def _redis(counts: dict[str, int]):
        r = MagicMock()
        r.incr.side_effect = lambda key: counts.get(key.split(":")[1], 1)
        return r

    @pytest.mark.asyncio
    async def test_device_buckets_are_used_with_a_valid_client_id(self):
        r = self._redis({})
        with patch("api.app.core.rate_limit._get_redis", return_value=r):
            await check_rate_limit(
                self._request("3f2b8c1e-9a7d-4c2e-b1f0-123456789abc"), api_key=None
            )
        keys = [c.args[0] for c in r.incr.call_args_list if c.args[0].startswith("rl:")]
        assert keys == [
            "rl:anon-device:41.207.1.1:3f2b8c1e-9a7d-4c2e-b1f0-123456789abc",
            "rl:anon-ip:41.207.1.1",
        ]

    @pytest.mark.asyncio
    async def test_neighbour_on_same_ip_is_not_blocked_by_another_device(self):
        # This device has used 3 requests; the shared IP has seen 60 in total:
        # under the old per-IP rule (20) it would be refused.
        r = self._redis({"anon-device": 3, "anon-ip": 60})
        with patch("api.app.core.rate_limit._get_redis", return_value=r):
            await check_rate_limit(self._request("device-aaaaaaaaaaaaaaaa"), api_key=None)

    @pytest.mark.asyncio
    async def test_device_over_its_quota_is_refused(self):
        r = self._redis({"anon-device": 21, "anon-ip": 30})
        with patch("api.app.core.rate_limit._get_redis", return_value=r):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit(self._request("device-aaaaaaaaaaaaaaaa"), api_key=None)
        assert exc.value.status_code == 429
        assert "20 requests" in exc.value.detail

    @pytest.mark.asyncio
    async def test_ip_ceiling_still_applies_to_forged_device_ids(self):
        r = self._redis({"anon-device": 1, "anon-ip": 151})
        with patch("api.app.core.rate_limit._get_redis", return_value=r):
            with pytest.raises(HTTPException) as exc:
                await check_rate_limit(self._request("forged-id-0000000000001"), api_key=None)
        assert "150 requests" in exc.value.detail

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_id", [None, "short", "has spaces in it!!!!", "x" * 65])
    async def test_without_a_valid_device_id_the_per_ip_quota_applies(self, bad_id):
        r = self._redis({})
        with patch("api.app.core.rate_limit._get_redis", return_value=r):
            await check_rate_limit(self._request(bad_id), api_key=None)
        keys = [c.args[0] for c in r.incr.call_args_list if c.args[0].startswith("rl:")]
        assert keys == ["rl:anon:41.207.1.1"]
