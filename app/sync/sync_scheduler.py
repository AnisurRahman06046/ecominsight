"""Scheduler for automated data synchronization."""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.sync.sync_manager import sync_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Scheduler for automated periodic synchronization."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False

    def start(self, interval_seconds: Optional[int] = None):
        """
        Start the sync scheduler.

        Args:
            interval_seconds: Sync interval in seconds (default from settings)
        """
        if not settings.sync_enabled:
            logger.info("Sync is disabled in settings")
            return

        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        interval = interval_seconds or settings.sync_interval

        logger.info(f"Starting sync scheduler with {interval}s interval")

        self.scheduler = AsyncIOScheduler()

        # Add sync job
        self.scheduler.add_job(
            func=self._run_sync,
            trigger=IntervalTrigger(seconds=interval),
            id='sync_job',
            name='MySQL to MongoDB sync',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("Sync scheduler started successfully")

    def stop(self):
        """Stop the sync scheduler."""
        if not self.is_running or not self.scheduler:
            logger.warning("Scheduler is not running")
            return

        logger.info("Stopping sync scheduler...")
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Sync scheduler stopped")

    async def _run_sync(self):
        """Execute sync job."""
        try:
            logger.info("=== Scheduled sync started ===")
            start_time = datetime.utcnow()

            # Run incremental sync
            result = await sync_manager.sync_all_tables(sync_type="incremental")

            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"=== Scheduled sync completed in {duration:.2f}s ===")
            logger.info(f"Summary: {result['successful_tables']} successful, "
                       f"{result['failed_tables']} failed, "
                       f"{result['total_records_synced']} records synced")

        except Exception as e:
            logger.error(f"Scheduled sync failed: {e}", exc_info=True)

    async def trigger_manual_sync(self, sync_type: str = "incremental"):
        """
        Trigger a manual sync.

        Args:
            sync_type: "full" or "incremental"

        Returns:
            Sync result
        """
        logger.info(f"Manual {sync_type} sync triggered")
        return await sync_manager.sync_all_tables(sync_type=sync_type)

    def get_status(self) -> dict:
        """Get scheduler status."""
        if not self.scheduler:
            return {
                "running": False,
                "message": "Scheduler not initialized"
            }

        jobs = []
        if self.is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None
                })

        return {
            "running": self.is_running,
            "interval_seconds": settings.sync_interval,
            "jobs": jobs
        }


# Global instance
sync_scheduler = SyncScheduler()
