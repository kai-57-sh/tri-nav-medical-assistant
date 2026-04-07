"""Tests for task coordinator orchestration."""

import pytest

from src.core.runtime.execution_context import ExecutionContext
from src.core.runtime.state_patch import apply_state_patch
from src.core.runtime.types import CapabilityResult


@pytest.mark.asyncio
async def test_task_coordinator_runs_all_success_tasks() -> None:
    from src.core.coordinator.task_coordinator import TaskCoordinator, TaskSpec

    async def consultation(ctx: ExecutionContext) -> dict[str, object]:
        return {"summary": f"consult:{ctx.text}"}

    async def triage(_: ExecutionContext) -> dict[str, object]:
        return {"level": "ROUTINE"}

    coordinator = TaskCoordinator(
        [
            TaskSpec(name="consultation", runner=consultation, required=True),
            TaskSpec(name="triage", runner=triage, required=True),
        ]
    )
    context = ExecutionContext(request_id="req-1", session_id="sess-1", text="咽痛")

    results = await coordinator.run(context)

    assert set(results.keys()) == {"consultation", "triage"}
    assert results["consultation"]["success"] is True
    assert results["triage"]["success"] is True
    assert results["triage"]["payload"]["level"] == "ROUTINE"


@pytest.mark.asyncio
async def test_task_coordinator_stops_after_required_failure() -> None:
    from src.core.coordinator.task_coordinator import TaskCoordinator, TaskSpec

    async def fail_required(_: ExecutionContext) -> dict[str, object]:
        raise RuntimeError("consultation failed")

    async def should_not_run(_: ExecutionContext) -> dict[str, object]:
        return {"ok": True}

    coordinator = TaskCoordinator(
        [
            TaskSpec(name="consultation", runner=fail_required, required=True),
            TaskSpec(name="triage", runner=should_not_run, required=True),
        ]
    )
    context = ExecutionContext(request_id="req-2", session_id="sess-2", text="胸闷")

    results = await coordinator.run(context)

    assert set(results.keys()) == {"consultation"}
    assert results["consultation"]["success"] is False
    assert "consultation failed" in str(results["consultation"]["error"])


@pytest.mark.asyncio
async def test_task_coordinator_continues_after_optional_failure() -> None:
    from src.core.coordinator.task_coordinator import TaskCoordinator, TaskSpec

    async def optional_fail(_: ExecutionContext) -> dict[str, object]:
        raise ValueError("weather unavailable")

    async def triage(_: ExecutionContext) -> dict[str, object]:
        return {"level": "URGENT"}

    coordinator = TaskCoordinator(
        [
            TaskSpec(name="weather", runner=optional_fail, required=False),
            TaskSpec(name="triage", runner=triage, required=True),
        ]
    )
    context = ExecutionContext(request_id="req-3", session_id="sess-3", text="咳嗽两周")

    results = await coordinator.run(context)

    assert set(results.keys()) == {"weather", "triage"}
    assert results["weather"]["success"] is False
    assert results["triage"]["success"] is True
    assert results["triage"]["payload"]["level"] == "URGENT"


def test_apply_state_patch_preserves_existing_values() -> None:
    seeded = ExecutionContext(
        request_id="req-state-patch-1",
        session_id="sess-state-patch-1",
        text="低热伴咽痛",
        turn_state={
            "consultation": {
                "summary": "已提取主诉：咽痛三天",
            }
        },
    )
    result = CapabilityResult(
        name="triage",
        success=True,
        payload={},
        state_patch={
            "triage": {
                "triage_level": "ROUTINE",
                "triage_reason": "生命体征平稳，建议门诊评估",
            }
        },
    )

    updated = apply_state_patch(seeded, result)

    assert updated.turn_state.consultation.summary == "已提取主诉：咽痛三天"
    assert updated.turn_state.triage.triage_level == "ROUTINE"
    assert updated.turn_state.triage.triage_reason == "生命体征平稳，建议门诊评估"
