"""
Enkel asyncio-baserad jobbkö.

Designad för att enkelt kunna ersättas med Celery + Redis utan
att ändra service-lagret. Jobbkön lever i processen och är
konfigurerad för max 1 parallellt GPU-jobb (MAX_CONCURRENT_JOBS).
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Job:
    meeting_id: str
    fn: Callable[..., Awaitable[None]]
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class JobQueue:
    def __init__(self, max_concurrent: int = 1) -> None:
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Jobbkö startad")

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Jobbkö stoppad")

    async def enqueue(self, job: Job) -> None:
        await self._queue.put(job)
        logger.info(f"Jobb köat: meeting_id={job.meeting_id} (kö-längd={self._queue.qsize()})")

    def queue_size(self) -> int:
        return self._queue.qsize()

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            async with self._semaphore:
                logger.info(f"Startar jobb: meeting_id={job.meeting_id}")
                try:
                    await job.fn(*job.args, **job.kwargs)
                    logger.info(f"Jobb klart: meeting_id={job.meeting_id}")
                except Exception as exc:
                    logger.exception(f"Jobb misslyckades: meeting_id={job.meeting_id}: {exc}")
                finally:
                    self._queue.task_done()


# Singleton – initieras i app startup
_queue_instance: JobQueue | None = None


def get_job_queue() -> JobQueue:
    global _queue_instance
    if _queue_instance is None:
        from app.core.config import get_settings
        settings = get_settings()
        _queue_instance = JobQueue(max_concurrent=settings.max_concurrent_jobs)
    return _queue_instance
