"""
APScheduler configuration and task scheduling management

Provides centralized scheduling for:
- Daily content fetching from sources
- Daily recommendation generation
- Manual job trigger support
- Job execution status tracking
"""

from datetime import datetime, timezone
from typing import Optional, Callable, Any
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.database import get_engine, get_db
from app.models.db.tables import SchedulerJob

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Get the global scheduler instance"""
    return _scheduler


def init_scheduler() -> AsyncIOScheduler:
    """
    Initialize and configure the APScheduler

    Returns:
        Configured AsyncIOScheduler instance
    """
    global _scheduler

    settings = get_settings()

    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled via configuration")
        return None

    # Configure job store using PostgreSQL
    engine = get_engine()
    jobstores = {
        'default': SQLAlchemyJobStore(engine=engine)
    }

    # Configure executor
    executors = {
        'default': {'type': 'threadpool', 'max_workers': 3}
    }

    # Configure job defaults
    job_defaults = {
        'coalesce': True,  # Coalesce missed jobs into one
        'max_instances': 1,  # Only one instance of each job at a time
        'misfire_grace_time': 3600,  # 1 hour grace time
    }

    # Create scheduler
    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=settings.SCHEDULER_TIMEZONE,
    )

    logger.info(f"Scheduler initialized with timezone: {settings.SCHEDULER_TIMEZONE}")
    return _scheduler


def register_scheduled_jobs(scheduler: AsyncIOScheduler) -> None:
    """
    Register all scheduled jobs with the scheduler

    Args:
        scheduler: The AsyncIOScheduler instance
    """
    settings = get_settings()

    # Parse fetch time (HH:MM)
    fetch_hour, fetch_minute = map(int, settings.SCHEDULER_FETCH_TIME.split(':'))

    # Register daily fetch job
    scheduler.add_job(
        func=run_scheduled_fetch,
        trigger=CronTrigger(hour=fetch_hour, minute=fetch_minute),
        id='daily_fetch',
        name='Daily Content Fetch',
        replace_existing=True,
    )
    logger.info(f"Registered daily_fetch job at {settings.SCHEDULER_FETCH_TIME}")

    # Parse recommend time (HH:MM)
    recommend_hour, recommend_minute = map(int, settings.SCHEDULER_RECOMMEND_TIME.split(':'))

    # Register daily recommend job
    scheduler.add_job(
        func=run_scheduled_recommend,
        trigger=CronTrigger(hour=recommend_hour, minute=recommend_minute),
        id='daily_recommend',
        name='Daily Recommendation Generation',
        replace_existing=True,
    )
    logger.info(f"Registered daily_recommend job at {settings.SCHEDULER_RECOMMEND_TIME}")

    # Parse email time (HH:MM)
    email_hour, email_minute = map(int, settings.SCHEDULER_EMAIL_TIME.split(':'))

    # Register daily email job
    scheduler.add_job(
        func=run_scheduled_email,
        trigger=CronTrigger(hour=email_hour, minute=email_minute),
        id='daily_email',
        name='Daily Email Digest',
        replace_existing=True,
    )
    logger.info(f"Registered daily_email job at {settings.SCHEDULER_EMAIL_TIME}")


def run_scheduled_fetch() -> None:
    """
    Wrapper for scheduled fetch task
    Records execution status and handles errors
    """
    from app.tasks.scheduler_jobs import fetch_daily

    batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    job_name = 'daily_fetch'

    logger.info(f"Starting scheduled fetch job for {batch_date}")

    # Check if already running for this batch
    if _is_job_running(job_name, batch_date):
        logger.warning(f"Job {job_name} for {batch_date} is already running, skipping")
        return

    # Record job start
    job_record = _record_job_start(job_name, batch_date)

    try:
        # Execute the actual task
        result = fetch_daily(batch_date=batch_date)

        # Record success
        _record_job_success(
            job_record_id=job_record.id,
            message=f"Fetched {result.get('items_new', 0)} new items",
            results=result
        )
        logger.info(f"Scheduled fetch job completed for {batch_date}")

    except Exception as e:
        logger.exception(f"Scheduled fetch job failed for {batch_date}")
        _record_job_failure(job_record.id, str(e))


def run_scheduled_recommend() -> None:
    """
    Wrapper for scheduled recommend task
    Records execution status and handles errors
    """
    from app.tasks.scheduler_jobs import recommend_daily

    batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    job_name = 'daily_recommend'

    logger.info(f"Starting scheduled recommend job for {batch_date}")

    # Check if already running for this batch
    if _is_job_running(job_name, batch_date):
        logger.warning(f"Job {job_name} for {batch_date} is already running, skipping")
        return

    # Record job start
    job_record = _record_job_start(job_name, batch_date)

    try:
        # Execute the actual task
        result = recommend_daily(batch_date=batch_date)

        # Record success
        _record_job_success(
            job_record_id=job_record.id,
            message=f"Generated {result.get('selected_count', 0)} recommendations",
            results=result
        )
        logger.info(f"Scheduled recommend job completed for {batch_date}")

    except Exception as e:
        logger.exception(f"Scheduled recommend job failed for {batch_date}")
        _record_job_failure(job_record.id, str(e))


def run_scheduled_email() -> None:
    """
    Wrapper for scheduled email task
    Records execution status and handles errors
    """
    from app.tasks.scheduler_jobs import send_daily_email

    batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    job_name = 'daily_email'

    logger.info(f"Starting scheduled email job for {batch_date}")

    # Check if already running for this batch
    if _is_job_running(job_name, batch_date):
        logger.warning(f"Job {job_name} for {batch_date} is already running, skipping")
        return

    # Record job start
    job_record = _record_job_start(job_name, batch_date)

    try:
        # Execute the actual task
        result = send_daily_email(batch_date=batch_date)

        # Record success
        if result.get('sent', False):
            _record_job_success(
                job_record_id=job_record.id,
                message=f"Sent email with {result.get('recommendation_count', 0)} recommendations",
                results=result
            )
            logger.info(f"Scheduled email job completed for {batch_date}")
        else:
            error_msg = result.get('error', result.get('message', 'Unknown error'))
            _record_job_failure(job_record.id, error_msg)
            logger.warning(f"Scheduled email job failed for {batch_date}: {error_msg}")

    except Exception as e:
        logger.exception(f"Scheduled email job failed for {batch_date}")
        _record_job_failure(job_record.id, str(e))


def _is_job_running(job_name: str, batch_date: str) -> bool:
    """
    Check if a job is already running for the given batch date

    Args:
        job_name: Name of the job
        batch_date: Batch date string (YYYY-MM-DD)

    Returns:
        True if job is running, False otherwise
    """
    try:
        with get_db() as db:
            existing = db.query(SchedulerJob).filter(
                SchedulerJob.job_name == job_name,
                SchedulerJob.batch_date == batch_date,
                SchedulerJob.status == 'running'
            ).first()
            return existing is not None
    except Exception as e:
        logger.error(f"Failed to check job status: {e}")
        return False


def _record_job_start(job_name: str, batch_date: str) -> SchedulerJob:
    """
    Record the start of a job execution

    Args:
        job_name: Name of the job
        batch_date: Batch date string (YYYY-MM-DD)

    Returns:
        Created SchedulerJob record
    """
    try:
        with get_db() as db:
            # Try to get existing job record or create new one
            job_record = db.query(SchedulerJob).filter(
                SchedulerJob.job_name == job_name,
                SchedulerJob.batch_date == batch_date
            ).first()

            if job_record:
                # Update existing record (retry)
                job_record.status = 'running'
                job_record.started_at = datetime.now(timezone.utc)
                job_record.error_message = None
                job_record.result_message = None
            else:
                # Create new record
                job_record = SchedulerJob(
                    id=uuid4(),
                    job_name=job_name,
                    batch_date=batch_date,
                    status='running',
                    started_at=datetime.now(timezone.utc),
                    job_params={},
                )
                db.add(job_record)

            db.commit()
            db.refresh(job_record)
            return job_record

    except Exception as e:
        logger.error(f"Failed to record job start: {e}")
        # Return a temporary object for error tracking
        return SchedulerJob(
            id=uuid4(),
            job_name=job_name,
            batch_date=batch_date,
            status='running',
            started_at=datetime.now(timezone.utc),
        )


def _record_job_success(job_record_id: Any, message: str, results: dict) -> None:
    """
    Record successful job completion

    Args:
        job_record_id: ID of the job record
        message: Success message
        results: Job result data
    """
    try:
        with get_db() as db:
            job_record = db.query(SchedulerJob).filter(
                SchedulerJob.id == job_record_id
            ).first()

            if job_record:
                finished_at = datetime.now(timezone.utc)
                duration = (finished_at - job_record.started_at).total_seconds() if job_record.started_at else None

                job_record.status = 'success'
                job_record.finished_at = finished_at
                job_record.duration_seconds = duration
                job_record.result_message = message
                job_record.job_results = results

                db.commit()

    except Exception as e:
        logger.error(f"Failed to record job success: {e}")


def _record_job_failure(job_record_id: Any, error_message: str) -> None:
    """
    Record job failure

    Args:
        job_record_id: ID of the job record
        error_message: Error message
    """
    try:
        with get_db() as db:
            job_record = db.query(SchedulerJob).filter(
                SchedulerJob.id == job_record_id
            ).first()

            if job_record:
                finished_at = datetime.now(timezone.utc)
                duration = (finished_at - job_record.started_at).total_seconds() if job_record.started_at else None

                job_record.status = 'failed'
                job_record.finished_at = finished_at
                job_record.duration_seconds = duration
                job_record.error_message = error_message

                db.commit()

    except Exception as e:
        logger.error(f"Failed to record job failure: {e}")


async def start_scheduler() -> None:
    """
    Start the scheduler and register all jobs
    Called during application startup
    """
    global _scheduler

    if _scheduler is None:
        _scheduler = init_scheduler()

    if _scheduler and not _scheduler.running:
        register_scheduled_jobs(_scheduler)
        _scheduler.start()
        logger.info("Scheduler started successfully")


async def stop_scheduler() -> None:
    """
    Stop the scheduler gracefully
    Called during application shutdown
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


def get_job_status(job_name: Optional[str] = None, batch_date: Optional[str] = None) -> list:
    """
    Get job execution status

    Args:
        job_name: Filter by job name
        batch_date: Filter by batch date

    Returns:
        List of SchedulerJob records
    """
    try:
        with get_db() as db:
            query = db.query(SchedulerJob)

            if job_name:
                query = query.filter(SchedulerJob.job_name == job_name)
            if batch_date:
                query = query.filter(SchedulerJob.batch_date == batch_date)

            # Order by started_at desc, limit to recent 50
            query = query.order_by(SchedulerJob.started_at.desc()).limit(50)

            return query.all()

    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        return []


def get_next_run_times() -> dict:
    """
    Get next scheduled run times for all jobs

    Returns:
        Dictionary mapping job_id to next_run_time
    """
    global _scheduler

    if not _scheduler or not _scheduler.running:
        return {}

    result = {}
    for job in _scheduler.get_jobs():
        if job.next_run_time:
            result[job.id] = {
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat(),
            }

    return result
