"""
Task Reminder Scheduler Service

Processes calendar tasks with reminder_minutes and sends push notifications via Web Push API.
This provides a fallback reminder system for planners who don't use Google Calendar.

Usage:
    Call the endpoint /scheduler/task-reminders via cron (every 5 minutes recommended):
    curl -X POST https://api.thespecialwedding.io/scheduler/task-reminders \
         -H "Authorization: Bearer <scheduler_token>"
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from app.core.database import mongo
from app.services.planner_notification_service import planner_notification_service

logger = logging.getLogger(__name__)


class TaskReminderService:
    """Service for processing and sending task reminder notifications via Web Push"""

    def __init__(self):
        self.tasks_collection = mongo.db["planner_tasks"]
        self.sent_reminders_collection = mongo.db["sent_task_reminders"]

    async def process_due_reminders(self, dry_run: bool = False) -> Dict:
        """
        Process all tasks with reminder_minutes that are due for notification.

        This checks tasks where:
        - reminder_minutes is set (> 0)
        - start_date or due_date is within reminder_minutes window from now
        - A reminder hasn't already been sent for this task in this window

        Args:
            dry_run: If True, only report what would be sent without actually sending

        Returns:
            Dict with processing results
        """
        now = datetime.now(timezone.utc)
        results = {
            "processed_at": now.isoformat(),
            "tasks_checked": 0,
            "reminders_sent": 0,
            "already_sent": 0,
            "errors": [],
            "dry_run": dry_run
        }

        try:
            # Find tasks with reminder_minutes set
            # Task is due for reminder if:
            # (start_date - reminder_minutes) <= now < start_date
            query = {
                "reminder_minutes": {"$exists": True, "$gt": 0},
                "status": {"$ne": "completed"},  # Don't remind for completed tasks
            }

            cursor = self.tasks_collection.find(query)
            tasks = await cursor.to_list(length=None)
            results["tasks_checked"] = len(tasks)

            for task in tasks:
                try:
                    await self._process_single_task(task, now, results, dry_run)
                except Exception as e:
                    error_msg = f"Error processing task {task.get('_id')}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)

            logger.info(
                f"Task reminder processing complete: {results['reminders_sent']} sent, "
                f"{results['already_sent']} skipped (already sent), "
                f"{results['tasks_checked']} checked"
            )

            return results

        except Exception as e:
            logger.error(f"Error in process_due_reminders: {str(e)}")
            results["errors"].append(str(e))
            return results

    async def _process_single_task(
        self,
        task: Dict,
        now: datetime,
        results: Dict,
        dry_run: bool
    ):
        """Process a single task for reminder notification"""
        task_id = str(task["_id"])
        reminder_minutes = task.get("reminder_minutes", 0)

        if not reminder_minutes:
            return

        # Get the relevant date (start_date or due_date)
        task_date = task.get("start_date") or task.get("due_date")
        if not task_date:
            return

        # Parse date if string
        if isinstance(task_date, str):
            try:
                task_date = datetime.fromisoformat(task_date.replace('Z', '+00:00'))
                if task_date.tzinfo:
                    task_date = task_date.replace(tzinfo=None)
            except ValueError:
                return

        # Calculate reminder window
        reminder_time = task_date - timedelta(minutes=reminder_minutes)

        # Check if we're in the reminder window (reminder_time <= now < task_date)
        # Give a 10-minute grace period after reminder_time
        window_end = reminder_time + timedelta(minutes=10)

        if not (reminder_time <= now <= window_end):
            # Not in reminder window
            return

        # Check if we already sent a reminder for this task in this period
        already_sent = await self._check_reminder_sent(task_id, reminder_time)
        if already_sent:
            results["already_sent"] += 1
            return

        # Send the reminder
        planner_email = task.get("planner_email")
        if not planner_email:
            return

        if dry_run:
            logger.info(f"[DRY RUN] Would send reminder for task '{task.get('title')}' to {planner_email}")
            results["reminders_sent"] += 1
            return

        # Send notification (triggers Web Push)
        try:
            await planner_notification_service.notify_task_reminder(
                planner_id=planner_email,
                task_title=task.get("title", "Untitled Task"),
                due_date=task_date.isoformat() if isinstance(task_date, datetime) else str(task_date),
                wedding_id=task.get("wedding_id"),
                task_id=task_id,
                reminder_minutes=reminder_minutes
            )

            # Record that we sent this reminder
            await self._record_reminder_sent(task_id, planner_email, reminder_time)

            results["reminders_sent"] += 1
            logger.info(f"Sent task reminder for '{task.get('title')}' to {planner_email}")

        except Exception as e:
            error_msg = f"Failed to send reminder for task {task_id}: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

    async def _check_reminder_sent(self, task_id: str, reminder_time: datetime) -> bool:
        """Check if a reminder was already sent for this task in this window"""
        # Allow up to 1 hour before reminder_time as the same "window"
        window_start = reminder_time - timedelta(hours=1)

        existing = await self.sent_reminders_collection.find_one({
            "task_id": task_id,
            "reminder_time": {"$gte": window_start, "$lte": reminder_time + timedelta(hours=1)}
        })

        return existing is not None

    async def _record_reminder_sent(
        self,
        task_id: str,
        planner_email: str,
        reminder_time: datetime
    ):
        """Record that a reminder was sent to prevent duplicates"""
        await self.sent_reminders_collection.insert_one({
            "task_id": task_id,
            "planner_email": planner_email,
            "reminder_time": reminder_time,
            "sent_at": datetime.now(timezone.utc)
        })

    async def cleanup_old_records(self, days_old: int = 7) -> int:
        """Remove old sent reminder records to prevent collection bloat"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
        result = await self.sent_reminders_collection.delete_many({
            "sent_at": {"$lt": cutoff}
        })
        logger.info(f"Cleaned up {result.deleted_count} old reminder records")
        return result.deleted_count


# Singleton instance
task_reminder_service = TaskReminderService()
