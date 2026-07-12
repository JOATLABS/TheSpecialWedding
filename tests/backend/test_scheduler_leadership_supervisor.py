"""Deterministic lifecycle tests for singleton background scheduler leadership."""

import asyncio

import pytest

import app.main as main


def _install_scheduler_task_factory(monkeypatch):
    generations: list[list[asyncio.Task]] = []
    started = asyncio.Event()

    async def child_scheduler() -> None:
        await asyncio.Event().wait()

    def start_scheduler_tasks() -> list[asyncio.Task]:
        tasks = [asyncio.create_task(child_scheduler())]
        generations.append(tasks)
        started.set()
        return tasks

    monkeypatch.setattr(
        main,
        "_start_background_scheduler_tasks",
        start_scheduler_tasks,
        raising=False,
    )
    return generations, started


async def _cancel(task: asyncio.Task) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_follower_retries_until_it_takes_over_scheduler_leadership(monkeypatch):
    generations, started = _install_scheduler_task_factory(monkeypatch)
    attempts = 0
    blocked = asyncio.Event()
    releases: list[str] = []

    async def acquire(holder_id: str) -> bool:
        nonlocal attempts
        assert holder_id == "replica-b"
        attempts += 1
        if attempts == 1:
            return False
        if attempts == 2:
            return True
        await blocked.wait()
        return False

    async def release(holder_id: str) -> None:
        releases.append(holder_id)

    monkeypatch.setattr(main, "_acquire_scheduler_leadership", acquire)
    monkeypatch.setattr(main, "_release_scheduler_leadership", release)
    monkeypatch.setattr(main, "SCHEDULER_LEADERSHIP_RETRY_SECONDS", 0, raising=False)
    monkeypatch.setattr(main, "SCHEDULER_LEADERSHIP_RENEWAL_SECONDS", 0, raising=False)

    supervisor = asyncio.create_task(main._background_scheduler_supervisor("replica-b"))
    await asyncio.wait_for(started.wait(), timeout=1)

    assert attempts >= 2
    assert len(generations) == 1

    await _cancel(supervisor)

    assert all(task.done() for task in generations[0])
    assert releases == ["replica-b"]


@pytest.mark.asyncio
async def test_transient_renewal_loss_cancels_children_before_safe_restart(monkeypatch):
    generations, _ = _install_scheduler_task_factory(monkeypatch)
    restarted = asyncio.Event()
    attempts = 0
    blocked = asyncio.Event()
    releases: list[str] = []

    async def acquire(_holder_id: str) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return True
        if attempts == 2:
            return False
        if attempts == 3:
            return True
        restarted.set()
        await blocked.wait()
        return False

    async def release(holder_id: str) -> None:
        releases.append(holder_id)

    original_start = main._start_background_scheduler_tasks

    def start_scheduler_tasks() -> list[asyncio.Task]:
        tasks = original_start()
        if len(generations) == 2:
            restarted.set()
        return tasks

    monkeypatch.setattr(
        main, "_start_background_scheduler_tasks", start_scheduler_tasks
    )
    monkeypatch.setattr(main, "_acquire_scheduler_leadership", acquire)
    monkeypatch.setattr(main, "_release_scheduler_leadership", release)
    monkeypatch.setattr(main, "SCHEDULER_LEADERSHIP_RETRY_SECONDS", 0, raising=False)
    monkeypatch.setattr(main, "SCHEDULER_LEADERSHIP_RENEWAL_SECONDS", 0, raising=False)

    supervisor = asyncio.create_task(main._background_scheduler_supervisor("replica-a"))
    await asyncio.wait_for(restarted.wait(), timeout=1)

    assert len(generations) == 2
    assert all(task.done() for task in generations[0])
    assert not generations[1][0].done()

    await _cancel(supervisor)

    assert all(task.done() for task in generations[1])
    assert releases == ["replica-a"]


@pytest.mark.asyncio
async def test_shutdown_after_leadership_loss_does_not_release_the_lease(
    monkeypatch,
):
    generations, _ = _install_scheduler_task_factory(monkeypatch)
    leadership_lost = asyncio.Event()
    retry_blocked = asyncio.Event()
    attempts = 0
    releases: list[str] = []

    async def acquire(_holder_id: str) -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return True
        if attempts == 2:
            leadership_lost.set()
            return False
        await retry_blocked.wait()
        return False

    async def release(holder_id: str) -> None:
        releases.append(holder_id)

    monkeypatch.setattr(main, "_acquire_scheduler_leadership", acquire)
    monkeypatch.setattr(main, "_release_scheduler_leadership", release)
    monkeypatch.setattr(main, "SCHEDULER_LEADERSHIP_RETRY_SECONDS", 0, raising=False)
    monkeypatch.setattr(main, "SCHEDULER_LEADERSHIP_RENEWAL_SECONDS", 0, raising=False)

    supervisor = asyncio.create_task(main._background_scheduler_supervisor("replica-a"))
    await asyncio.wait_for(leadership_lost.wait(), timeout=1)
    while not generations[0][0].done():
        await asyncio.sleep(0)

    await _cancel(supervisor)

    assert releases == []
