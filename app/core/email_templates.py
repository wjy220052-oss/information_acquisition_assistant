"""
Email template rendering

Provides Jinja2-based email template rendering for:
- Daily digest emails (HTML and plain text)
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.logging import get_logger
from app.services.recommendation.explainer import RecommendationExplainer, ExplanationContext

logger = get_logger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "email"


class EmailTemplateRenderer:
    """Renders email templates using Jinja2"""

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_daily_digest(
        self,
        recommendations: List[Any],
        date: Optional[str] = None,
        dashboard_url: str = "http://localhost:8000",
    ) -> Dict[str, str]:
        """
        Render daily digest email templates

        Args:
            recommendations: List of Recommendation objects with joined Article data
            date: Date string (defaults to today)
            dashboard_url: URL to the dashboard

        Returns:
            Dictionary with 'html' and 'text' keys containing rendered content
        """
        if date is None:
            date = datetime.now().strftime("%Y年%m月%d日")

        # Generate explanations for each recommendation
        explainer = RecommendationExplainer()
        recs_with_explanation = []
        total = len(recommendations)

        for rec in recommendations:
            article = rec['article'] if isinstance(rec, dict) else rec.article
            score = rec['score'] if isinstance(rec, dict) else rec.score
            rank = rec['rank'] if isinstance(rec, dict) else rec.rank

            context = ExplanationContext(
                title=getattr(article, 'title', ''),
                source_name=getattr(getattr(article, 'source', None), 'name', None),
                author_name=getattr(getattr(article, 'author', None), 'name', None),
                content_type=getattr(article, 'content_type', None),
                quality_level=getattr(article, 'quality_level', None),
                classification_tags=getattr(article, 'classification_tags', None),
                reading_time_minutes=getattr(article, 'reading_time_minutes', None),
                score=float(score) if score else 0.0,
                rank=rank if rank else 1,
                total_recommendations=total,
            )

            explanation = explainer.explain(context)

            # Add explanation to recommendation dict
            if isinstance(rec, dict):
                rec_copy = rec.copy()
                rec_copy['explanation'] = explanation
            else:
                # Create a dict wrapper for ORM object
                rec_copy = {
                    'article': article,
                    'score': score,
                    'rank': rank,
                    'explanation': explanation,
                }

            recs_with_explanation.append(rec_copy)

        # Prepare template context
        context = {
            "recommendations": recs_with_explanation,
            "date": date,
            "dashboard_url": dashboard_url,
        }

        try:
            # Render HTML template
            html_template = self.env.get_template("daily_digest.html")
            html_body = html_template.render(**context)

            # Render text template
            text_template = self.env.get_template("daily_digest.txt")
            text_body = text_template.render(**context)

            return {
                "html": html_body,
                "text": text_body,
                "subject": f"每日阅读推荐 - {date}",
            }

        except Exception as e:
            logger.exception(f"Failed to render email templates: {e}")
            raise

    def render_test_email(self) -> Dict[str, str]:
        """
        Render a test email

        Returns:
            Dictionary with 'html' and 'text' keys
        """
        date = datetime.now().strftime("%Y年%m月%d日")

        context = {
            "recommendations": [],
            "date": date,
            "dashboard_url": "http://localhost:8000",
        }

        html_template = self.env.get_template("daily_digest.html")
        html_body = html_template.render(**context)

        text_template = self.env.get_template("daily_digest.txt")
        text_body = text_template.render(**context)

        return {
            "html": html_body,
            "text": text_body,
            "subject": f"[测试] 邮件服务配置成功 - {date}",
        }


def get_template_renderer() -> EmailTemplateRenderer:
    """Get a configured EmailTemplateRenderer instance"""
    return EmailTemplateRenderer()
