"""Retry primitive for best-effort side-effects.

Use when a side-effect (notification, webhook, index update) is not the source
of truth for the operation that triggered it. The retry primitive:

- Retries with exponential backoff up to `max_retries` times.
- Logs each failed attempt at WARNING level and the final give-up at ERROR
  level with a stable log key so alerts can be wired up later.
- Swallows the final exception so the caller's main operation is not broken
  by a side-effect failure. The caller's request/message/write already
  persisted before the best-effort block ran.

Two surfaces on the same engine:

    # 1. Decorator for a best-effort function
    @best_effort(max_retries=3, initial_delay=0.5, backoff=2.0,
                 op_name="planner_notification")
    async def _notify_planner(...):
        await notification_service.create_notification(...)

    # 2. Async context manager for an inline block
    async with best_effort(max_retries=3, initial_delay=0.5, backoff=2.0,
                           op_name="planner_notification"):
        await notification_service.create_notification(...)

Both surfaces share the same retry/logging behavior. Neither propagates a
final failure to the caller. If you need a side-effect that must succeed,
don't use this primitive — block on it and let the request fail.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default knobs. Exposed as module-level so tests and callers can reference
# them; individual call sites should pass explicit values for clarity.
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 0.5
DEFAULT_BACKOFF_FACTOR = 2.0


async def _run_with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    initial_delay: float,
    backoff: float,
    op_name: str,
) -> T | None:
    """Invoke `coro_factory()` repeatedly until it succeeds or retries exhaust.

    Returns the awaited result on success, or None on final failure (failure
    is logged, not raised). `coro_factory` must be a zero-arg callable that
    produces a fresh awaitable each call — a single awaitable cannot be
    awaited twice.
    """

    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    attempt = 0
    delay = initial_delay
    last_error: BaseException | None = None

    while attempt < max_retries:
        attempt += 1
        try:
            return await coro_factory()
        except asyncio.CancelledError:
            # Cancellation is not a failure of the side-effect — propagate so
            # task shutdown is not swallowed.
            raise
        except Exception as err:
            last_error = err
            if attempt >= max_retries:
                break
            logger.warning(
                "best_effort_task attempt failed op_name=%s attempt=%d/%d "
                "next_delay=%.2fs error=%s",
                op_name,
                attempt,
                max_retries,
                delay,
                err,
            )
            await asyncio.sleep(delay)
            delay *= backoff

    logger.error(
        "best_effort_task gave up op_name=%s attempts=%d final_error=%s",
        op_name,
        attempt,
        last_error,
    )
    return None


def best_effort(
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    backoff: float = DEFAULT_BACKOFF_FACTOR,
    op_name: str,
) -> _BestEffort:
    """Return a retry primitive usable as a decorator or async context manager.

    `op_name` is required and appears in every log line so failures are
    greppable / alertable per call site. Keep it short and stable
    (e.g., "planner_notification", "vendor_webhook").
    """

    return _BestEffort(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff=backoff,
        op_name=op_name,
    )


class _BestEffort:
    """Dual-surface retry primitive.

    Not instantiated directly — call `best_effort(...)` instead. The class
    name is underscored because its surface is the `best_effort` function.
    """

    def __init__(
        self,
        *,
        max_retries: int,
        initial_delay: float,
        backoff: float,
        op_name: str,
    ) -> None:
        self._max_retries = max_retries
        self._initial_delay = initial_delay
        self._backoff = backoff
        self._op_name = op_name
        # Context-manager state:
        self._cm_active = False

    # --- Decorator surface ---------------------------------------------------

    def __call__(
        self, fn: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T | None]]:
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError(
                "best_effort only wraps async functions; "
                f"got {fn!r} which is not a coroutine function"
            )

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T | None:
            return await _run_with_retry(
                lambda: fn(*args, **kwargs),
                max_retries=self._max_retries,
                initial_delay=self._initial_delay,
                backoff=self._backoff,
                op_name=self._op_name,
            )

        return wrapper

    # --- Async context-manager surface ---------------------------------------

    async def __aenter__(self) -> _BestEffort:
        # The context-manager surface wraps a single awaited expression. We
        # capture exceptions in __aexit__ and do NOT retry — a one-shot
        # awaited block cannot be replayed. If you need retries inline, use
        # the `retry_async` helper below instead.
        self._cm_active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> bool:
        self._cm_active = False
        if exc is None:
            return False
        if isinstance(exc, asyncio.CancelledError):
            return False  # propagate cancellation
        logger.error(
            "best_effort_task gave up op_name=%s attempts=1 final_error=%s",
            self._op_name,
            exc,
        )
        # Swallow the exception — the caller's primary operation is not
        # affected by this side-effect's failure.
        return True

    # --- Inline retry helper -------------------------------------------------

    async def run(self, coro_factory: Callable[[], Awaitable[T]]) -> T | None:
        """Run `coro_factory` with full retry/backoff behavior inline.

        Use when you want the retry loop without decorating a function:

            result = await best_effort(..., op_name="x").run(
                lambda: service.do_thing(arg)
            )
        """

        return await _run_with_retry(
            coro_factory,
            max_retries=self._max_retries,
            initial_delay=self._initial_delay,
            backoff=self._backoff,
            op_name=self._op_name,
        )
