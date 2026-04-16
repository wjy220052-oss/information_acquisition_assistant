"""
Recommendation explainer - generates human-readable reasons for recommendations

MVP version: Rule-based explanation generation
Future versions: LLM-based personalized explanations
"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class ExplanationContext:
    """Context for generating recommendation explanations"""
    title: str
    source_name: Optional[str]
    author_name: Optional[str]
    content_type: Optional[str]
    quality_level: Optional[str]
    classification_tags: Optional[List[str]]
    reading_time_minutes: Optional[int]
    score: float
    rank: int
    total_recommendations: int


class RecommendationExplainer:
    """
    Generates explanation strings for recommendations

    Uses a simple rule-based approach for MVP:
    - Quality-based: "高质量内容"
    - Rank-based: "今日首选"
    - Source-based: "来自 xxx 的精选"
    - Type-based: "技术文章/讨论帖"
    - Depth-based: "深度长文"

    Future: LLM-based personalized explanations
    """

    def __init__(self):
        self.quality_phrases = {
            'high': '高质量内容',
            'medium': '值得一读',
            'low': '观点独特',
        }

        self.rank_phrases = {
            1: '今日首选',
            2: '强烈推荐',
            3: '值得一看',
        }

        self.content_type_phrases = {
            'article': '深度长文',
            'discussion': '热门讨论',
            'tutorial': '实用教程',
            'news': '最新资讯',
            'review': '深度评论',
        }

    def explain(self, context: ExplanationContext) -> str:
        """
        Generate a recommendation explanation

        Args:
            context: ExplanationContext with article and recommendation data

        Returns:
            Human-readable explanation string
        """
        reasons = []

        # 1. Rank-based (highest priority for top items)
        if context.rank <= 3:
            reasons.append(self.rank_phrases.get(context.rank, '推荐阅读'))

        # 2. Quality-based
        if context.quality_level == 'high':
            reasons.append(self.quality_phrases['high'])
        elif context.quality_level == 'medium' and len(reasons) < 2:
            reasons.append(self.quality_phrases['medium'])

        # 3. Source-based
        if context.source_name and len(reasons) < 2:
            source_phrase = self._get_source_phrase(context.source_name)
            if source_phrase:
                reasons.append(source_phrase)

        # 4. Type-based
        if context.content_type and len(reasons) < 2:
            type_phrase = self.content_type_phrases.get(context.content_type)
            if type_phrase:
                reasons.append(type_phrase)

        # 5. Depth-based (reading time)
        if context.reading_time_minutes and context.reading_time_minutes >= 15 and len(reasons) < 2:
            reasons.append('深度长文')
        elif context.reading_time_minutes and context.reading_time_minutes <= 3 and len(reasons) < 2:
            reasons.append('短小精悍')

        # 6. Author-based
        if context.author_name and len(reasons) < 2:
            # Only add author for known quality authors
            if any(name in context.author_name for name in ['阮一峰']):
                reasons.append(f'{context.author_name} 出品')

        # Combine reasons
        if not reasons:
            return '根据您的阅读偏好推荐'

        if len(reasons) == 1:
            return reasons[0]

        # Join with separator
        return ' · '.join(reasons[:2])

    def _get_source_phrase(self, source_name: str) -> Optional[str]:
        """Get source-specific phrase"""
        source_phrases = {
            'v2ex': '来自 V2EX 社区',
            'sspai': '少数派精选',
            'ruanyf_weekly': '阮一峰周刊推荐',
            'rsshub_zhihu': '知乎精选',
            'rsshub_douban': '豆瓣精选',
        }

        # Try exact match
        if source_name in source_phrases:
            return source_phrases[source_name]

        # Try partial match
        for key, phrase in source_phrases.items():
            if key in source_name.lower():
                return phrase

        return None

    def explain_from_recommendation(
        self,
        recommendation,
        article,
    ) -> str:
        """
        Convenience method to generate explanation from ORM objects

        Args:
            recommendation: Recommendation ORM object
            article: Article ORM object

        Returns:
            Explanation string
        """
        context = ExplanationContext(
            title=article.title,
            source_name=article.source.name if article.source else None,
            author_name=article.author.name if article.author else None,
            content_type=article.content_type,
            quality_level=article.quality_level,
            classification_tags=article.classification_tags or [],
            reading_time_minutes=article.reading_time_minutes,
            score=float(recommendation.score) if recommendation.score else 0.0,
            rank=recommendation.rank,
            total_recommendations=10,  # Default
        )

        return self.explain(context)


def get_explainer() -> RecommendationExplainer:
    """Get a configured RecommendationExplainer instance"""
    return RecommendationExplainer()
