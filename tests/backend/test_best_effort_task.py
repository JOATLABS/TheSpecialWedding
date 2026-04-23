import asyncio
import logging

import pytest

from app.utils.best_effort_task import best_effort


# --- Decorator surface -------------------------------------------------------


@pytest.mark.asyncio
async def test_decorator_returns_result_on_first_try_success():
    calls = {"count": 0}

    @best_effort(max_retries=3, initial_delay=0, backoff=1.0, op_name="test_ok")
    async def ok() -> str:
        calls["count"] += 1
        return "ok"

    result = await ok()

    assert result == "ok"
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_decorator_retries_then_succeeds(caplog):
    caplog.set_level(logging.WARNING)
    calls = {"count": 0}

    @best_effort(max_retries=3, initial_delay=0, backoff=1.0, op_name="test_retry_ok")
    async def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise RuntimeError("boom")
        return "eventually"

    result = await flaky()

    assert result == "eventually"
    assert calls["count"] == 2
    # One WARNING logged for the first failed attempt, no ERROR because we
    # eventually succeeded.
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(warnings) == 1
    assert "op_name=test_retry_ok" in warnings[0].getMessage()
    assert "attempt=1/3" in warnings[0].getMessage()
    assert errors == []


@pytest.mark.asyncio
async def test_decorator_gives_up_after_max_retries_and_returns_none(caplog):
    caplog.set_level(logging.WARNING)
    calls = {"count": 0}

    @best_effort(max_retries=3, initial_delay=0, backoff=1.0, op_name="test_give_up")
    async def always_fails() -> str:
        calls["count"] += 1
        raise RuntimeError("still broken")

    result = await always_fails()

    assert result is None  # never raises to caller
    assert calls["count"] == 3

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    # 2 warnings for attempts 1 and 2, then 1 error on final give-up
    assert len(warnings) == 2
    assert len(errors) == 1
    final = errors[0].getMessage()
    assert "op_name=test_give_up" in final
    assert "attempts=3" in final
    assert "final_error=still broken" in final


@pytest.mark.asyncio
async def test_decorator_never_propagates_exception_to_caller():
    @best_effort(
        max_retries=2, initial_delay=0, backoff=1.0, op_name="test_no_propagate"
    )
    async def always_fails() -> None:
        raise ValueError("should not escape")

    # If this raised, pytest would catch and fail the test. The contract is
    # that best_effort swallows the final failure.
    result = await always_fails()
    assert result is None


@pytest.mark.asyncio
async def test_decorator_propagates_cancellation():
    @best_effort(max_retries=3, initial_delay=0, backoff=1.0, op_name="test_cancel")
    async def cancelled() -> None:
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await cancelled()


@pytest.mark.asyncio
async def test_decorator_rejects_sync_function():
    with pytest.raises(TypeError):

        @best_effort(max_retries=3, initial_delay=0, backoff=1.0, op_name="test_sync")
        def sync_fn() -> None:  # pragma: no cover
            pass


# --- Context-manager surface -------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_succeeds_silently():
    async with best_effort(
        max_retries=3, initial_delay=0, backoff=1.0, op_name="test_cm_ok"
    ):
        # Simulate a successful side-effect
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_context_manager_swallows_exception_and_logs_error(caplog):
    caplog.set_level(logging.ERROR)

    async with best_effort(
        max_retries=3, initial_delay=0, backoff=1.0, op_name="test_cm_fail"
    ):
        raise RuntimeError("side effect failed")

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    msg = errors[0].getMessage()
    assert "op_name=test_cm_fail" in msg
    assert "final_error=side effect failed" in msg


@pytest.mark.asyncio
async def test_context_manager_propagates_cancellation():
    with pytest.raises(asyncio.CancelledError):
        async with best_effort(
            max_retries=3,
            initial_delay=0,
            backoff=1.0,
            op_name="test_cm_cancel",
        ):
            raise asyncio.CancelledError()


# --- Inline `.run()` helper --------------------------------------------------


@pytest.mark.asyncio
async def test_run_helper_retries_and_succeeds():
    calls = {"count": 0}

    async def maybe():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("not yet")
        return 42

    result = await best_effort(
        max_retries=5, initial_delay=0, backoff=1.0, op_name="test_run"
    ).run(lambda: maybe())

    assert result == 42
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_run_helper_gives_up_returns_none():
    calls = {"count": 0}

    async def never():
        calls["count"] += 1
        raise RuntimeError("nope")

    result = await best_effort(
        max_retries=3, initial_delay=0, backoff=1.0, op_name="test_run_fail"
    ).run(lambda: never())

    assert result is None
    assert calls["count"] == 3


# --- Configuration validation ------------------------------------------------


@pytest.mark.asyncio
async def test_max_retries_must_be_positive():
    @best_effort(max_retries=0, initial_delay=0, backoff=1.0, op_name="bad")
    async def fn() -> None:
        pass

    with pytest.raises(ValueError):
        await fn()


# --- Backoff behavior --------------------------------------------------------


@pytest.mark.asyncio
async def test_exponential_backoff_delays_grow(monkeypatch):
    """The delay between attempts should multiply by `backoff` each retry."""

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    attempts = {"count": 0}

    @best_effort(max_retries=4, initial_delay=0.1, backoff=2.0, op_name="test_backoff")
    async def always_fails() -> None:
        attempts["count"] += 1
        raise RuntimeError("boom")

    await always_fails()

    # Three sleeps between four attempts: 0.1, 0.2, 0.4
    assert sleep_calls == pytest.approx([0.1, 0.2, 0.4])
    assert attempts["count"] == 4
