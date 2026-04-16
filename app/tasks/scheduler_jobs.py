"""
Scheduled job wrappers for daily tasks

Provides safe wrappers for fetch and recommend tasks that can be called
by the scheduler. Handles:
- Error catching and logging
- Result formatting for scheduler job records
- Task-specific configuration
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from uuid import uuid4

from app.core.logging import get_logger
from app.services.sources.v2ex import V2EXAdapter
from app.services.sources.ruanyf_weekly import RuanyfWeeklyAdapter
from app.services.sources.solidot import SolidotAdapter
from app.tasks.fetch import FetchTask
from app.tasks.recommend import run_recommend_task
from app.core.mailer import get_mailer
from app.core.email_templates import get_template_renderer
from app.core.database import get_db
from app.repositories.recommendation_repository import RecommendationRepository
from app.repositories.article_repository import ArticleRepository
from app.models.db.tables import EmailLog, Source, Author


class SimpleNamespace:
    """Simple object for attribute access"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

logger = get_logger(__name__)


def fetch_daily(batch_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Daily fetch task - fetches content from all configured sources

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with task results
    """
    if batch_date is None:
        batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    logger.info(f"Starting daily fetch task for {batch_date}")

    results = {
        'batch_date': batch_date,
        'sources': [],
        'total_fetched': 0,
        'total_new': 0,
        'total_updated': 0,
        'total_failed': 0,
        'errors': [],
    }

    # Define sources to fetch from
    # V2EX: 实时技术讨论
    # 阮一峰 weekly: 每周科技周刊
    # Solidot: 每日科技新闻/开源/AI 资讯
    sources_config = [
        {'name': 'v2ex', 'adapter': V2EXAdapter, 'params': {'mode': 'latest'}, 'limit': 20},
        {'name': 'ruanyf_weekly', 'adapter': RuanyfWeeklyAdapter, 'params': {}, 'limit': 10},
        {'name': 'solidot', 'adapter': SolidotAdapter, 'params': {}, 'limit': 10},
    ]

    for source_config in sources_config:
        source_name = source_config['name']
        logger.info(f"Fetching from {source_name}")

        try:
            # Create adapter
            adapter = source_config['adapter'](config=source_config.get('params', {}))

            # Create and run fetch task
            task = FetchTask(
                adapter=adapter,
                enable_classification=True,
                enable_quality_scoring=True,
            )

            fetch_result = task.run(limit=source_config.get('limit', 10))

            # Record results
            source_result = {
                'name': source_name,
                'success': fetch_result.success,
                'fetched': fetch_result.items_fetched,
                'new': fetch_result.items_new,
                'updated': fetch_result.items_updated,
                'failed': fetch_result.items_failed,
                'duration_seconds': fetch_result.duration_seconds,
            }
            results['sources'].append(source_result)

            # Accumulate totals
            results['total_fetched'] += fetch_result.items_fetched
            results['total_new'] += fetch_result.items_new
            results['total_updated'] += fetch_result.items_updated
            results['total_failed'] += fetch_result.items_failed

            if fetch_result.errors:
                results['errors'].extend(fetch_result.errors)

            if fetch_result.success:
                logger.info(
                    f"Fetch from {source_name} completed: "
                    f"{fetch_result.items_new} new, {fetch_result.items_updated} updated"
                )
            else:
                logger.warning(f"Fetch from {source_name} reported failure")

        except Exception as e:
            error_msg = f"Failed to fetch from {source_name}: {str(e)}"
            logger.exception(error_msg)
            results['errors'].append(error_msg)
            results['sources'].append({
                'name': source_name,
                'success': False,
                'error': str(e),
            })

    # Overall success if at least one source succeeded
    results['success'] = any(s.get('success', False) for s in results['sources'])

    logger.info(
        f"Daily fetch task completed: {results['total_new']} new, "
        f"{results['total_updated']} updated from {len(results['sources'])} sources"
    )

    return results


def recommend_daily(batch_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Daily recommend task - generates recommendations for the day

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with task results
    """
    if batch_date is None:
        batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    logger.info(f"Starting daily recommend task for {batch_date}")

    try:
        # Run the recommend task
        result = run_recommend_task(
            batch_date=batch_date,
            min_overall_score=0.35,
            max_recommendations=10,
        )

        # Format results for scheduler record
        results = {
            'batch_date': result.batch_date,
            'success': True,
            'recommendation_type': result.recommendation_type,
            'total_candidates': result.total_candidates,
            'filtered_count': result.filtered_count,
            'selected_count': result.selected_count,
            'skipped_count': result.skipped_count,
        }

        logger.info(
            f"Daily recommend task completed: {result.selected_count} recommendations "
            f"generated from {result.filtered_count} candidates"
        )

        return results

    except Exception as e:
        error_msg = f"Daily recommend task failed: {str(e)}"
        logger.exception(error_msg)

        return {
            'batch_date': batch_date,
            'success': False,
            'error': str(e),
        }


def trigger_fetch_sync(batch_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for manual fetch trigger

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with task results
    """
    return fetch_daily(batch_date)


def trigger_recommend_sync(batch_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for manual recommend trigger

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with task results
    """
    return recommend_daily(batch_date)


def send_daily_email(batch_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Daily email task - sends email digest with recommendations

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with task results
    """
    from app.core.config import get_settings

    if batch_date is None:
        batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    logger.info(f"Starting daily email task for {batch_date}")

    settings = get_settings()
    mailer = get_mailer()

    # Check email configuration
    if not mailer.config.is_configured:
        logger.warning("Email service not configured, skipping email send")
        return {
            'batch_date': batch_date,
            'success': False,
            'error': 'Email service not configured',
            'sent': False,
        }

    # Create email log record
    email_log_id = None
    try:
        with get_db() as db:
            email_log = EmailLog(
                id=uuid4(),
                batch_date=batch_date,
                email_type='daily_digest',
                status='pending',
                to_email=mailer.config.to_email,
                from_email=mailer.config.from_email,
                subject=f'每日阅读推荐 - {batch_date}',
            )
            db.add(email_log)
            db.commit()
            email_log_id = email_log.id
    except Exception as e:
        logger.error(f"Failed to create email log: {e}")

    try:
        # Get recommendations with article data (extract all data within session)
        with get_db() as db:
            rec_repo = RecommendationRepository(db)
            recommendations = rec_repo.get_recommendations_for_date(
                batch_date=batch_date,
                recommendation_type='daily_digest',
            )

            # Extract all data into plain dictionaries while in session
            recs_with_data = []
            for rec in recommendations:
                article = rec.article
                if article:
                    # Extract article data into a plain dict
                    article_data = {
                        'title': article.title,
                        'url': article.url,
                        'summary': article.summary,
                        'content_type': article.content_type,
                        'word_count': article.word_count,
                        'reading_time_minutes': article.reading_time_minutes,
                        'publish_time': article.publish_time,
                        'classification_tags': article.classification_tags if hasattr(article, 'classification_tags') else None,
                    }

                    # Extract source data
                    if article.source_id:
                        source = db.query(Source).filter(Source.id == article.source_id).first()
                        if source:
                            article_data['source'] = {
                                'name': source.name,
                                'domain': source.domain,
                            }
                        else:
                            article_data['source'] = None
                    else:
                        article_data['source'] = None

                    # Extract author data
                    if article.author_id:
                        author = db.query(Author).filter(Author.id == article.author_id).first()
                        if author:
                            article_data['author'] = {
                                'name': author.name,
                                'username': author.username,
                            }
                        else:
                            article_data['author'] = None
                    else:
                        article_data['author'] = None

                    # Wrap in SimpleNamespace for template attribute access
                    article_obj = SimpleNamespace(**article_data)
                    recs_with_data.append({
                        'article': article_obj,
                        'score': float(rec.score),
                        'rank': rec.rank,
                    })

        # Render email templates
        renderer = get_template_renderer()
        email_content = renderer.render_daily_digest(
            recommendations=recs_with_data,
            date=batch_date,
            dashboard_url=settings.DASHBOARD_URL,
        )

        # Send email
        result = mailer.send_email(
            subject=email_content['subject'],
            html_body=email_content['html'],
            text_body=email_content['text'],
        )

        # Update email log
        if email_log_id:
            try:
                with get_db() as db:
                    log = db.query(EmailLog).filter(EmailLog.id == email_log_id).first()
                    if log:
                        if result['success']:
                            log.status = 'sent'
                            log.sent_at = datetime.now(timezone.utc)
                            log.recommendation_count = len(recs_with_data)
                        else:
                            log.status = 'failed'
                            log.failed_at = datetime.now(timezone.utc)
                            log.error_message = result.get('message', 'Unknown error')
                        db.commit()
            except Exception as e:
                logger.error(f"Failed to update email log: {e}")

        if result['success']:
            logger.info(f"Daily email sent successfully for {batch_date} with {len(recs_with_data)} recommendations")
        else:
            logger.error(f"Failed to send daily email for {batch_date}: {result.get('message')}")

        return {
            'batch_date': batch_date,
            'success': result['success'],
            'sent': result['success'],
            'recommendation_count': len(recs_with_data),
            'message': result.get('message'),
        }

    except Exception as e:
        logger.exception(f"Daily email task failed for {batch_date}: {e}")

        # Update email log on failure
        if email_log:
            try:
                with get_db() as db:
                    log = db.query(EmailLog).filter(EmailLog.id == email_log.id).first()
                    if log:
                        log.status = 'failed'
                        log.failed_at = datetime.now(timezone.utc)
                        log.error_message = str(e)
                        db.commit()
            except Exception as log_err:
                logger.error(f"Failed to update email log: {log_err}")

        return {
            'batch_date': batch_date,
            'success': False,
            'sent': False,
            'error': str(e),
        }


def send_test_email() -> Dict[str, Any]:
    """
    Send a test email to verify configuration

    Returns:
        Dictionary with task results
    """
    logger.info("Sending test email")

    mailer = get_mailer()

    # Check email configuration
    if not mailer.config.is_configured:
        return {
            'success': False,
            'error': 'Email service not configured',
            'sent': False,
        }

    try:
        # Render test email
        renderer = get_template_renderer()
        email_content = renderer.render_test_email()

        # Send email
        result = mailer.send_email(
            subject=email_content['subject'],
            html_body=email_content['html'],
            text_body=email_content['text'],
        )

        logger.info(f"Test email result: {result['message']}")

        return {
            'success': result['success'],
            'sent': result['success'],
            'message': result.get('message'),
        }

    except Exception as e:
        logger.exception(f"Test email failed: {e}")
        return {
            'success': False,
            'sent': False,
            'error': str(e),
        }


def trigger_email_sync(batch_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for manual email trigger

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today

    Returns:
        Dictionary with task results
    """
    return send_daily_email(batch_date)
