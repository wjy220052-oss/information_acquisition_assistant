"""
Scheduler API routes

Provides endpoints for:
- Manual job triggering
- Job status querying
- Next run time information
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.scheduler import (
    get_scheduler,
    get_job_status,
    get_next_run_times,
    _is_job_running,
)
from app.core.database import get_db
from app.core.mailer import verify_email_config, get_email_config_status
from app.models.db.tables import SchedulerJob, EmailLog
from app.tasks.scheduler_jobs import trigger_fetch_sync, trigger_recommend_sync, send_test_email, send_daily_email

logger = get_logger(__name__)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


# Pydantic models for request/response
class JobTriggerRequest(BaseModel):
    """Request model for manual job trigger"""
    batch_date: Optional[str] = Field(
        None,
        description="Batch date (YYYY-MM-DD), defaults to today",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )


class JobTriggerResponse(BaseModel):
    """Response model for job trigger"""
    success: bool
    message: str
    job_name: str
    batch_date: str
    started_at: str


class JobInfo(BaseModel):
    """Job information model"""
    id: str
    job_name: str
    batch_date: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    result_message: Optional[str] = None
    error_message: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    """Response model for scheduler status"""
    scheduler_running: bool
    jobs: List[Dict[str, Any]]
    recent_executions: List[JobInfo]


class NextRunTimeResponse(BaseModel):
    """Response model for next run times"""
    jobs: Dict[str, Dict[str, str]]


class TestEmailResponse(BaseModel):
    """Response model for test email"""
    success: bool
    message: str
    sent: bool


class EmailLogInfo(BaseModel):
    """Email log information model"""
    id: str
    batch_date: str
    email_type: str
    status: str
    to_email: str
    subject: str
    sent_at: Optional[str] = None
    failed_at: Optional[str] = None
    recommendation_count: int
    error_message: Optional[str] = None


class EmailLogsResponse(BaseModel):
    """Response model for email logs"""
    logs: List[EmailLogInfo]


class EmailConfigCheckResponse(BaseModel):
    """Response model for email configuration check"""
    is_configured: bool
    state: str  # 'not_configured', 'partially_configured', 'configured'
    configured_count: int
    total_required: int
    missing_fields: List[str]
    config_preview: Dict[str, Any]
    help_message: str
    help_url: str


def _run_fetch_job_task(batch_date: str) -> None:
    """
    Background task wrapper for fetch job

    Args:
        batch_date: Batch date string
    """
    job_name = 'manual_fetch'

    try:
        result = trigger_fetch_sync(batch_date=batch_date)

        if result.get('success', False):
            logger.info(f"Manual fetch job completed for {batch_date}")
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Manual fetch job failed for {batch_date}: {error_msg}")

    except Exception as e:
        logger.exception(f"Manual fetch job failed for {batch_date}")


def _run_recommend_job_task(batch_date: str) -> None:
    """
    Background task wrapper for recommend job

    Args:
        batch_date: Batch date string
    """
    try:
        result = trigger_recommend_sync(batch_date=batch_date)

        if result.get('success', False):
            logger.info(f"Manual recommend job completed for {batch_date}")
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Manual recommend job failed for {batch_date}: {error_msg}")

    except Exception as e:
        logger.exception(f"Manual recommend job failed for {batch_date}")


@router.post(
    "/trigger/fetch",
    response_model=JobTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger content fetch",
    description="Trigger the daily content fetch job manually. Runs in background."
)
async def trigger_fetch(
    background_tasks: BackgroundTasks,
    request: Optional[JobTriggerRequest] = None,
) -> JobTriggerResponse:
    """
    Manually trigger the fetch job

    Args:
        background_tasks: FastAPI background tasks
        request: Optional job trigger request with batch_date

    Returns:
        Job trigger response indicating job started
    """
    batch_date = request.batch_date if request else None
    if batch_date is None:
        batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    job_name = 'manual_fetch'

    # Check if already running
    if _is_job_running(job_name, batch_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fetch job for {batch_date} is already running"
        )

    # Start background task
    background_tasks.add_task(_run_fetch_job_task, batch_date)

    logger.info(f"Manual fetch job triggered for {batch_date}")

    return JobTriggerResponse(
        success=True,
        message="Fetch job started in background",
        job_name=job_name,
        batch_date=batch_date,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post(
    "/trigger/recommend",
    response_model=JobTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger recommendation generation",
    description="Trigger the daily recommendation generation job manually. Runs in background."
)
async def trigger_recommend(
    background_tasks: BackgroundTasks,
    request: Optional[JobTriggerRequest] = None,
) -> JobTriggerResponse:
    """
    Manually trigger the recommend job

    Args:
        background_tasks: FastAPI background tasks
        request: Optional job trigger request with batch_date

    Returns:
        Job trigger response indicating job started
    """
    batch_date = request.batch_date if request else None
    if batch_date is None:
        batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    job_name = 'manual_recommend'

    # Check if already running
    if _is_job_running(job_name, batch_date):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recommend job for {batch_date} is already running"
        )

    # Start background task
    background_tasks.add_task(_run_recommend_job_task, batch_date)

    logger.info(f"Manual recommend job triggered for {batch_date}")

    return JobTriggerResponse(
        success=True,
        message="Recommend job started in background",
        job_name=job_name,
        batch_date=batch_date,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="Get scheduler status",
    description="Get the current status of the scheduler and recent job executions."
)
async def get_scheduler_status() -> SchedulerStatusResponse:
    """
    Get scheduler status and recent job executions

    Returns:
        Scheduler status response with job info
    """
    scheduler = get_scheduler()
    scheduler_running = scheduler is not None and scheduler.running

    # Get next run times
    next_runs = get_next_run_times()
    jobs_info = []

    if scheduler_running:
        for job in scheduler.get_jobs():
            job_info = {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
            }
            jobs_info.append(job_info)

    # Get recent executions - extract all data before session closes
    recent_jobs_data = []
    with get_db() as db:
        jobs = db.query(SchedulerJob).order_by(
            SchedulerJob.started_at.desc()
        ).limit(50).all()

        # Extract data while session is active
        for job in jobs:
            recent_jobs_data.append({
                'id': str(job.id),
                'job_name': job.job_name,
                'batch_date': job.batch_date,
                'status': job.status,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'finished_at': job.finished_at.isoformat() if job.finished_at else None,
                'duration_seconds': float(job.duration_seconds) if job.duration_seconds else None,
                'result_message': job.result_message,
                'error_message': job.error_message,
            })

    recent_executions = [JobInfo(**job_data) for job_data in recent_jobs_data]

    return SchedulerStatusResponse(
        scheduler_running=scheduler_running,
        jobs=jobs_info,
        recent_executions=recent_executions,
    )


@router.get(
    "/jobs/{job_name}",
    response_model=List[JobInfo],
    summary="Get job execution history",
    description="Get execution history for a specific job name."
)
async def get_job_history(
    job_name: str,
    batch_date: Optional[str] = None,
) -> List[JobInfo]:
    """
    Get execution history for a specific job

    Args:
        job_name: Name of the job
        batch_date: Optional batch date filter

    Returns:
        List of job execution records
    """
    # Query and extract data while session is active
    jobs_data = []
    with get_db() as db:
        query = db.query(SchedulerJob).filter(SchedulerJob.job_name == job_name)

        if batch_date:
            query = query.filter(SchedulerJob.batch_date == batch_date)

        jobs = query.order_by(SchedulerJob.started_at.desc()).limit(50).all()

        # Extract data while session is active
        for job in jobs:
            jobs_data.append({
                'id': str(job.id),
                'job_name': job.job_name,
                'batch_date': job.batch_date,
                'status': job.status,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'finished_at': job.finished_at.isoformat() if job.finished_at else None,
                'duration_seconds': float(job.duration_seconds) if job.duration_seconds else None,
                'result_message': job.result_message,
                'error_message': job.error_message,
            })

    return [JobInfo(**job_data) for job_data in jobs_data]


@router.post(
    "/trigger/email",
    response_model=TestEmailResponse,
    status_code=status.HTTP_200_OK,
    summary="Send test email",
    description="Send a test email with today's recommendations to verify email configuration."
)
async def trigger_test_email() -> TestEmailResponse:
    """
    Send a test email with today's recommendations to verify email configuration.

    Returns:
        Test email response with success status
    """
    from datetime import datetime, timezone

    # First verify configuration
    config_check = verify_email_config()
    if not config_check["success"]:
        return TestEmailResponse(
            success=False,
            message=config_check["message"],
            sent=False,
        )

    # Send daily email with today's recommendations
    batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    result = send_daily_email(batch_date=batch_date)

    return TestEmailResponse(
        success=result.get("success", False),
        message=result.get("message", result.get("error", "Unknown result")),
        sent=result.get("sent", False),
    )


@router.get(
    "/emails",
    response_model=EmailLogsResponse,
    summary="Get email sending history",
    description="Get history of sent emails with their status."
)
async def get_email_logs(
    batch_date: Optional[str] = None,
    limit: int = 50,
) -> EmailLogsResponse:
    """
    Get email sending history

    Args:
        batch_date: Optional filter by batch date
        limit: Maximum number of records to return

    Returns:
        List of email log records
    """
    logs_data = []
    with get_db() as db:
        query = db.query(EmailLog)

        if batch_date:
            query = query.filter(EmailLog.batch_date == batch_date)

        logs = query.order_by(EmailLog.created_at.desc()).limit(limit).all()

        for log in logs:
            logs_data.append({
                'id': str(log.id),
                'batch_date': log.batch_date,
                'email_type': log.email_type,
                'status': log.status,
                'to_email': log.to_email,
                'subject': log.subject,
                'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                'failed_at': log.failed_at.isoformat() if log.failed_at else None,
                'recommendation_count': log.recommendation_count,
                'error_message': log.error_message,
            })

    return EmailLogsResponse(logs=[EmailLogInfo(**log_data) for log_data in logs_data])


@router.get(
    "/email/config-check",
    response_model=EmailConfigCheckResponse,
    summary="Check email configuration status",
    description="Verify email service configuration without attempting to send."
)
async def check_email_config() -> EmailConfigCheckResponse:
    """
    Get detailed email configuration status

    Returns:
        EmailConfigCheckResponse with configuration details including:
        - is_configured: bool - Whether all required fields are set
        - state: str - 'not_configured', 'partially_configured', or 'configured'
        - configured_count: int - Number of configured fields
        - total_required: int - Total number of required fields
        - missing_fields: List[str] - List of missing field names
        - config_preview: Dict - Masked preview of current configuration
        - help_message: str - Human-readable help message
        - help_url: str - URL to documentation
    """
    status = get_email_config_status()

    return EmailConfigCheckResponse(
        is_configured=status['is_configured'],
        state=status['state'],
        configured_count=status['configured_count'],
        total_required=status['total_required'],
        missing_fields=status['missing_fields'],
        config_preview=status['config_preview'],
        help_message=status['help_message'],
        help_url=status['help_url'],
    )
