"""
Home page route

Provides the main landing page for the application.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Configure templates
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Home page - displays today's recommendations

    Shows a list of recommended articles for today with their
    scores, summaries, and links to original content.
    """
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    recommendations = []
    error = None

    try:
        with get_db() as db:
            # Query today's recommendations with article details
            query = text("""
                SELECT
                    r.id as rec_id,
                    r.rank,
                    r.score,
                    a.id as article_id,
                    a.title,
                    a.original_content as summary,
                    a.content_type,
                    a.url,
                    s.name as source_name
                FROM recommendations r
                JOIN articles a ON r.article_id = a.id
                JOIN sources s ON a.source_id = s.id
                WHERE r.batch_date = :batch_date
                AND r.recommendation_type = 'daily_digest'
                AND r.status = 'pending'
                ORDER BY r.rank ASC
            """)

            result = db.execute(query, {"batch_date": today})
            rows = result.fetchall()

            for row in rows:
                recommendations.append({
                    "rec_id": str(row.rec_id),
                    "rank": row.rank,
                    "score": float(row.score),
                    "article_id": str(row.article_id),
                    "title": row.title,
                    "summary": row.summary[:200] + "..." if row.summary and len(row.summary) > 200 else (row.summary or ""),
                    "content_type": row.content_type,
                    "url": row.url,
                    "source_name": row.source_name,
                })

            logger.info(f"Home page loaded with {len(recommendations)} recommendations for {today}")

    except Exception as e:
        logger.error(f"Failed to load recommendations for home page: {e}")
        error = "获取失败"

    from starlette.templating import _TemplateResponse as TemplateResponse
    return TemplateResponse(
        template=templates.get_template("index.html"),
        context={
            "request": request,
            "date": today,
            "recommendations": recommendations,
            "error": error,
        }
    )
