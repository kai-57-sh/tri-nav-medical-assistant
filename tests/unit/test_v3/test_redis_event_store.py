import pytest
from src.core.state.redis_event_store import RedisEventStore


@pytest.mark.asyncio
async def test_redis_event_store_prefixes_session_key_and_stores_event_history(mocker) -> None:
    fake = mocker.AsyncMock()
    fake.load_cached_result.return_value = None
    store = RedisEventStore(fake)
    event = {"event_type": "runtime_started"}

    await store.append("sess-1", event)

    fake.load_cached_result.assert_awaited_once_with("events:sess-1")
    fake.cache_external_result.assert_awaited_once_with(
        cache_key="events:sess-1",
        result={"events": [event]},
        ttl=3600,
    )


@pytest.mark.asyncio
async def test_redis_event_store_uses_expected_payload_and_ttl(mocker) -> None:
    fake = mocker.AsyncMock()
    store = RedisEventStore(fake)

    event = {"event_type": "runtime_started", "message": "启动"}
    await store.append("sess-1", event)

    fake.cache_external_result.assert_awaited_once_with(
        cache_key="events:sess-1",
        result={"events": [event]},
        ttl=3600,
    )


@pytest.mark.asyncio
async def test_redis_event_store_appends_event_history(mocker) -> None:
    fake = mocker.AsyncMock()
    fake.load_cached_result.side_effect = [None, {"events": [{"event_type": "runtime_started"}]}]
    store = RedisEventStore(fake)

    await store.append("sess-1", {"event_type": "runtime_started"})
    await store.append("sess-1", {"event_type": "capability_completed"})

    assert fake.cache_external_result.await_count == 2
    assert fake.cache_external_result.await_args_list[1].kwargs == {
        "cache_key": "events:sess-1",
        "result": {
            "events": [
                {"event_type": "runtime_started"},
                {"event_type": "capability_completed"},
            ]
        },
        "ttl": 3600,
    }
