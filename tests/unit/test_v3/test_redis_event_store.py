import json

import pytest
from src.core.state.redis_event_store import RedisEventStore


@pytest.mark.asyncio
async def test_redis_event_store_prefixes_session_key(mocker) -> None:
    fake = mocker.AsyncMock()
    store = RedisEventStore(fake)
    await store.append("sess-1", {"event_type": "runtime_started"})
    fake.cache_external_result.assert_awaited()


@pytest.mark.asyncio
async def test_redis_event_store_uses_expected_payload_and_ttl(mocker) -> None:
    fake = mocker.AsyncMock()
    store = RedisEventStore(fake)

    event = {"event_type": "runtime_started", "message": "启动"}
    await store.append("sess-1", event)

    fake.cache_external_result.assert_awaited_once_with(
        cache_key="events:sess-1",
        result={"last_event": json.dumps(event, ensure_ascii=False)},
        ttl=3600,
    )
