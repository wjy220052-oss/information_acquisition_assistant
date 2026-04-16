"""
Content Quality Scorer

Rule-based quality scoring for content based on various signals.
"""

import logging
import re
from typing import Optional, Dict, List
from datetime import datetime, timedelta

from app.models.schemas.content import (
    QualityScore,
    QualityLevel,
    ContentMetadata,
    SourceItem,
)

logger = logging.getLogger(__name__)


class ContentQualityScorer:
    """
    Rule-based content quality scorer

    Scores content based on:
    - Content completeness and structure
    - Source credibility
    - Author reputation
    - Engagement signals
    - Content freshness

    Supports content type differentiation for discussion vs article.
    """

    # Standard weights for articles/long-form content
    ARTICLE_WEIGHTS = {
        'completeness': 0.25,    # 内容完整性
        'structure': 0.20,       # 结构清晰度
        'depth': 0.25,           # 内容深度
        'credibility': 0.20,     # 可信度
        'engagement': 0.10,      # 互动质量
    }

    # Discussion-specific weights (more tolerant of short content)
    # Note: engagement weight is high but base engagement score is lower for discussions
    DISCUSSION_WEIGHTS = {
        'completeness': 0.20,    # 降低字数要求
        'structure': 0.15,       # 降低结构要求
        'depth': 0.20,           # 信息密度
        'credibility': 0.25,     # 略升（来源信任对讨论很重要）
        'engagement': 0.20,      # 适中（问题清晰度算在engagement里）
    }

    def __init__(self):
        """Initialize scorer with quality rules"""
        # Define source trust scores
        self.source_trust_scores = {
            # High trust sources
            'sspai': 0.9,
            'zhihu': 0.8,
            'v2ex': 0.7,
            'douban': 0.75,
            # Medium trust
            'medium': 0.7,
            'dev.to': 0.7,
            # Low trust (placeholder for future)
            # 'unknown': 0.5,
        }

        # Define minimum thresholds
        self.min_word_count = 100      # 最少字数
        self.max_word_count_soft = 5000  # 软上限
        self.min_paragraph_count = 3    # 最少段落数

    def _detect_content_type(
        self,
        source_item: SourceItem,
        content: str,
        metadata: ContentMetadata
    ) -> str:
        """
        Detect content type based on source and content features.

        Primary: Use explicit content_type if provided
        Fallback: Auto-detect based on source_id + text features
        """
        # Check for discussion indicators in source or content
        discussion_sources = {'v2ex', 'reddit', 'hn', 'lobsters'}

        if source_item.source_id in discussion_sources:
            # V2EX-like sources: check if content looks like a question/discussion
            title = source_item.title or ""
            content_lower = (content or "").lower()

            # Question indicators
            question_patterns = [
                '如何', '怎么', '请问', '请教', '求解',
                '为什么', '什么是', '有没有', '推荐',
                '?', '？',
                'help', 'how to', 'what is', 'recommend',
            ]

            has_question = any(p in title or p in content_lower
                              for p in question_patterns)

            # Short content indicator (discussions are typically shorter)
            is_short = metadata.word_count < 500

            # Discussion format indicators
            has_list_format = any(marker in content for marker in ['1.', '2.', '- ', '* '])

            if has_question or (is_short and has_list_format):
                return "discussion"

        return "article"

    def _is_discussion_type(
        self,
        content_type: Optional[str],
        source_item: SourceItem,
        content: str,
        metadata: ContentMetadata
    ) -> bool:
        """Check if content should be scored as discussion."""
        # Explicit content_type takes priority
        if content_type == "discussion":
            return True
        if content_type == "article":
            return False

        # Auto-detect
        detected = self._detect_content_type(source_item, content, metadata)
        return detected == "discussion"

    def _score_question_clarity(self, source_item: SourceItem, content: str) -> float:
        """
        Score how clear and specific the question is.
        For discussion content only.
        """
        score = 0.0
        title = source_item.title or ""
        content_text = content or ""

        # Has clear question word in title
        question_words = ['如何', '怎么', '请问', '为什么', '什么是', '有没有', '推荐']
        if any(w in title for w in question_words):
            score += 0.3

        # Title is specific (not too vague)
        if len(title) > 10 and len(title) < 60:
            score += 0.2

        # Content provides context
        if len(content_text) > 50:
            score += 0.2

        # Has specific details (lists, examples, attempted solutions)
        if any(marker in content_text for marker in ['1.', '2.', '已经', '尝试过']):
            score += 0.15

        # Has clear expected outcome
        if any(phrase in content_text for phrase in ['谢谢', '求助', '请教', '请问']):
            score += 0.15

        return min(1.0, score)

    def _score_practical_value(self, source_item: SourceItem, content: str) -> float:
        """
        Score practical value for discussion content.
        How actionable/usable is this discussion for others?
        """
        score = 0.0
        title = source_item.title or ""
        content_text = content or ""

        # Technical/tool-related questions have high practical value
        practical_keywords = [
            'macOS', 'Linux', 'Windows', 'Python', 'JavaScript', 'Go',
            'Docker', 'K8s', 'Kubernetes', 'Nginx', 'PostgreSQL', 'MySQL',
            'Redis', 'Git', 'VS Code', 'IDE', '编辑器', '配置',
            '安装', '部署', '优化', '报错', '解决',
        ]
        if any(kw in title or kw in content_text for kw in practical_keywords):
            score += 0.4

        # Clear problem statement
        if any(phrase in content_text for phrase in ['报错', '错误', '问题', 'bug', 'error']):
            score += 0.2

        # Shows effort (already tried something)
        if any(phrase in content_text for phrase in ['已经', '尝试', '试过', '用了']):
            score += 0.2

        # Has constraints/requirements
        if any(marker in content_text for marker in ['需要', '要求', '限制', '环境']):
            score += 0.1

        return min(1.0, score)

    def score(self,
              source_item: SourceItem,
              content: str = "",
              metadata: Optional[ContentMetadata] = None,
              content_type: Optional[str] = None) -> QualityScore:
        """
        Score content quality

        Args:
            source_item: The source content item
            content: Full content text (if available)
            metadata: Content metadata (if available)
            content_type: Explicit content type ('discussion' or 'article')

        Returns:
            QualityScore with detailed breakdown
        """
        quality = QualityScore()

        # Prepare metadata
        if metadata is None:
            metadata = self._extract_metadata(source_item, content)

        # Detect content type
        is_discussion = self._is_discussion_type(content_type, source_item, content, metadata)

        # Select appropriate weights
        if is_discussion:
            weights = self.DISCUSSION_WEIGHTS
        else:
            weights = self.ARTICLE_WEIGHTS

        # Calculate individual score components
        if is_discussion:
            completeness_score = self._score_completeness_discussion(content, metadata)
            structure_score = self._score_structure_discussion(content, metadata)
            depth_score = self._score_depth_discussion(content, metadata)
        else:
            completeness_score = self._score_completeness(source_item, content, metadata)
            structure_score = self._score_structure(content, metadata)
            depth_score = self._score_depth(content, metadata)

        credibility_score = self._score_credibility(source_item, metadata)
        engagement_score = self._score_engagement(source_item, metadata)

        # Add discussion-specific scoring boosts (minimal)
        if is_discussion:
            question_clarity = self._score_question_clarity(source_item, content)
            practical_value = self._score_practical_value(source_item, content)

            # Very conservative boost - discussions get slight depth boost for practical value
            depth_score = min(1.0, depth_score + practical_value * 0.1)

        # Calculate weighted overall score
        overall_score = (
            completeness_score * weights['completeness'] +
            structure_score * weights['structure'] +
            depth_score * weights['depth'] +
            credibility_score * weights['credibility'] +
            engagement_score * weights['engagement']
        )

        quality.overall_score = max(0.0, min(1.0, overall_score))
        quality.quality_level = self._determine_quality_level(quality.overall_score)
        quality.completeness_score = completeness_score
        quality.structure_score = structure_score
        quality.depth_score = depth_score
        quality.credibility_score = credibility_score
        quality.engagement_score = engagement_score

        # Set flags
        quality.is_original = self._check_originality(source_item, metadata)
        quality.has_citation = self._check_citations(content)
        quality.is_clickbait = self._detect_clickbait(source_item.title or "", source_item.summary or "")
        quality.contains_sensitive = self._detect_sensitive_content(content)

        return quality

    def _extract_metadata(self, source_item: SourceItem, content: str) -> ContentMetadata:
        """Extract content metadata if not provided"""
        metadata = ContentMetadata()

        if content:
            # Word count
            metadata.word_count = len(content)

            # Structural features
            metadata.paragraph_count = content.count('\n\n') + 1
            metadata.quote_count = content.count('> ') + content.count('》')

            # Check for code blocks
            metadata.has_code = '```' in content

            # Check for images
            metadata.has_images = '![' in content or 'img' in content.lower()

            # External links
            link_pattern = r'https?://[^\s]+'
            links = re.findall(link_pattern, content)
            metadata.has_external_links = len(links) > 0
            metadata.link_count = len(links)

        # Content age
        if source_item.publish_time:
            now = datetime.now(source_item.publish_time.tzinfo)
            metadata.content_age_hours = (now - source_item.publish_time).total_seconds() / 3600

        # Source trust score
        metadata.source_trust_score = self.source_trust_scores.get(
            source_item.source_id, 0.5
        )

        # Author reputation (placeholder)
        if source_item.author_name:
            # Simple heuristic: known authors get higher score
            if '专栏' in source_item.author_name or '编辑' in source_item.author_name:
                metadata.author_reputation = 0.9
            elif '专家' in source_item.author_name or '认证' in source_item.author_name:
                metadata.author_reputation = 0.8
            else:
                metadata.author_reputation = 0.6

        return metadata

    def _score_completeness(self, content_or_source_item, metadata_or_content, metadata: ContentMetadata = None) -> float:
        """Score content completeness based on length and coverage

        Supports two calling conventions:
        1. _score_completeness(content: str, metadata: ContentMetadata) - test compatibility
        2. _score_completeness(source_item: SourceItem, content: str, metadata: ContentMetadata) - full feature
        """
        score = 0.0

        # Detect which calling convention is used
        if metadata is None:
            # Old style: _score_completeness(content, metadata)
            content = content_or_source_item if isinstance(content_or_source_item, str) else ""
            metadata = metadata_or_content if isinstance(metadata_or_content, ContentMetadata) else ContentMetadata()
            source_item = None
        else:
            # New style: _score_completeness(source_item, content, metadata)
            source_item = content_or_source_item if hasattr(content_or_source_item, 'source_id') else None
            content = metadata_or_content if isinstance(metadata_or_content, str) else ""

        # Word count score - more generous scale
        word_count = metadata.word_count
        if word_count >= 100:
            if word_count < 300:
                score += 0.4
            elif word_count < 1000:
                score += 0.7
            else:
                score += 0.95
        elif word_count >= 50:
            score += 0.2

        # Has summary bonus (if source_item available)
        if source_item and source_item.summary and len(source_item.summary) >= 50:
            if word_count <= 1000:
                score += 0.05

        return min(1.0, score)

    def _score_completeness_discussion(self, content: str, metadata: ContentMetadata) -> float:
        """
        Score completeness for discussion content (more tolerant of short content).
        Discussion quality is not about length but about sufficient context.
        """
        score = 0.0
        word_count = metadata.word_count

        # Discussion-specific scoring (conservative)
        if word_count >= 200:
            score += 0.6   # Good score for substantial discussions
        elif word_count >= 100:
            score += 0.5   # Moderate score for medium discussions
        elif word_count >= 50:
            score += 0.4   # Acceptable for short but valid questions
        elif word_count >= 20:
            score += 0.3   # Minimum viable question

        # Information density bonus (small)
        if word_count > 0:
            has_specifics = any(marker in content for marker in
                              ['1.', '2.', '已经', '尝试', '版本', '环境', '报错'])
            if has_specifics:
                score += 0.05

        return min(1.0, score)

    def _score_structure_discussion(self, content: str, metadata: ContentMetadata) -> float:
        """
        Score structure for discussion (different criteria than articles).
        Discussions don't need traditional structure but should be readable.
        """
        score = 0.0

        # Basic readability (has some line breaks or natural flow)
        if metadata.paragraph_count >= 2:
            score += 0.3
        elif metadata.paragraph_count >= 1:
            score += 0.2

        # Has organized points (common in good discussions)
        if content:
            list_items = len(re.findall(r'^\s*\d+\.', content, re.MULTILINE))
            if list_items >= 2:
                score += 0.25
            elif list_items >= 1:
                score += 0.15

            # Has clear question and context separation
            if '？' in content or '?' in content:
                score += 0.15

            # Reasonable sentence structure (not just fragments)
            sentences = [s.strip() for s in re.split(r'[。！？.!?]', content) if s.strip()]
            if len(sentences) >= 2:
                score += 0.2

        return min(1.0, score)

    def _score_depth_discussion(self, content: str, metadata: ContentMetadata) -> float:
        """
        Score depth for discussion (focus on information density, not complexity).
        """
        score = 0.0

        # Technical keywords indicate useful discussion
        if content:
            technical_indicators = [
                '版本', '配置', '环境', '参数', '报错', '错误码',
                'Python', 'JavaScript', 'Docker', 'Git', 'Linux',
                'macOS', 'Windows', '数据库', 'API', '框架',
            ]
            tech_count = sum(1 for term in technical_indicators if term in content)
            if tech_count >= 3:
                score += 0.25
            elif tech_count >= 1:
                score += 0.15

        # Has attempted solutions (shows effort)
        effort_indicators = ['已经', '尝试', '试过', '用了', '安装了']
        if content and any(e in content for e in effort_indicators):
            score += 0.15

        # Has code snippets (valuable in discussions)
        if metadata.has_code:
            score += 0.15

        # Has external references
        if metadata.has_external_links:
            score += 0.1

        return min(1.0, score)

    def _score_structure(self, content: str, metadata: ContentMetadata) -> float:
        """Score content structure and readability"""
        score = 0.0

        # Paragraph structure (traditional paragraphs or markdown sections)
        if metadata.paragraph_count >= self.min_paragraph_count:
            score += 0.4
        elif content:
            # Alternative: count markdown sections as structure
            # Count headings, list items, or code blocks as structural elements
            structural_elements = 0
            if re.search(r'^#+\s', content, re.MULTILINE):
                structural_elements += 1
            if re.search(r'^\s*\d+\.', content, re.MULTILINE):
                structural_elements += 1
            if metadata.has_code:
                structural_elements += 1
            if metadata.paragraph_count >= 1:
                structural_elements += 1
            # Give partial credit for structural elements
            score += min(0.4, structural_elements * 0.15)

        # Has introduction (first paragraph/section should be reasonable)
        if content:
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            if lines and len(lines[0]) > 30:
                score += 0.2

        # Has conclusion (last paragraph ends properly)
        if content and (content.strip().endswith('。') or content.strip().endswith('!') or
                       content.strip().endswith('?') or content.strip().endswith('.')):
            score += 0.2

        # Use of headings (if present)
        if re.search(r'^#+\s', content, re.MULTILINE):
            score += 0.2

        return min(1.0, score)

    def _score_depth(self, content: str, metadata: ContentMetadata) -> float:
        """Score content depth and sophistication"""
        score = 0.0

        # Code blocks (for technical content)
        if metadata.has_code:
            score += 0.35

        # Quotes or citations
        if metadata.quote_count > 0:
            score += 0.25

        # External links (shows research)
        if metadata.link_count > 0:
            if metadata.link_count >= 3:
                score += 0.35
            elif metadata.link_count >= 1:
                score += 0.2

        # Images (visual content)
        if metadata.has_images:
            score += 0.15

        # Complex vocabulary (simplified check)
        if content:
            # Count technical terms
            technical_terms = [
                '算法', '架构', '原理', '机制', '实现', '优化',
                '分析', '策略', '方案', '设计', '模式', '框架'
            ]
            found_terms = sum(1 for term in technical_terms if term in content)
            if found_terms >= 3:
                score += 0.25
            elif found_terms >= 1:
                score += 0.1

        # List items indicate structured content
        if content and re.search(r'^\s*\d+\.', content, re.MULTILINE):
            score += 0.1

        return min(1.0, score)

    def _score_credibility(self, source_item: SourceItem, metadata: ContentMetadata) -> float:
        """Score content credibility based on source and author"""
        score = metadata.source_trust_score

        # Author reputation boost
        if metadata.author_reputation > 0.8:
            score += 0.1
        elif metadata.author_reputation > 0.6:
            score += 0.05

        # Recent content (less likely to be outdated)
        if metadata.content_age_hours < 24:
            score += 0.1
        elif metadata.content_age_hours < 168:  # 1 week
            score += 0.05

        return min(1.0, score)

    def _score_engagement(self, source_item: SourceItem, metadata: ContentMetadata) -> float:
        """Score based on engagement signals"""
        score = 0.3  # Base score - assume reasonable engagement

        # Check for engagement metrics
        if metadata.view_count and metadata.view_count > 1000:
            score += 0.25
        elif metadata.view_count and metadata.view_count > 100:
            score += 0.15

        if metadata.comment_count and metadata.comment_count > 10:
            score += 0.25
        elif metadata.comment_count and metadata.comment_count > 0:
            score += 0.1

        if metadata.like_count and metadata.like_count > 100:
            score += 0.2
        elif metadata.like_count and metadata.like_count > 10:
            score += 0.1

        # Title quality (avoid clickbait)
        if source_item.title and not self._detect_clickbait(source_item.title, ""):
            score += 0.15

        # Good author bonus
        if source_item.author_name and len(source_item.author_name) > 0:
            score += 0.1

        return min(1.0, score)

    def _determine_quality_level(self, score: float) -> QualityLevel:
        """Determine quality level based on score"""
        if score >= 0.8:
            return QualityLevel.HIGH
        elif score >= 0.6:
            return QualityLevel.MEDIUM
        else:
            return QualityLevel.LOW

    def _check_originality(self, source_item: SourceItem, metadata: ContentMetadata) -> bool:
        """Check if content appears to be original"""
        # Simple heuristic: if it's from a discussion forum, might not be original
        if source_item.source_id in ['v2ex', 'zhihu']:
            # Check if title looks like a question or discussion
            title = source_item.title or ""
            if '?' in title or '如何' in title or '怎么' in title:
                return False
        return True

    def _check_citations(self, content: str) -> bool:
        """Check if content has citations"""
        if not content:
            return False

        # Look for citation patterns
        citation_patterns = [
            r'\[[0-9]+\]',  # [1], [2], etc.
            r'\([^)]*\d{4}[^)]*\)',  # (Author 2023)
            r'来源：',  # 来源：
            r'参考：',  # 参考：
            r'via @',  # via @username
        ]

        for pattern in citation_patterns:
            if re.search(pattern, content):
                return True

        return False

    def _detect_clickbait(self, title: str, summary: str) -> bool:
        """Detect clickbait patterns"""
        clickbait_keywords = [
            '震惊', '惊呆了', '太可怕了', '万万没想到', '竟然',
            '第一名', '必看', '紧急', '突发', '刚刚',
            '99%的人不知道', '秘密', '真相', '曝光',
            '速看', '不看后悔', '惊爆', '独家', '内幕'
        ]

        title_lower = title.lower()
        for keyword in clickbait_keywords:
            if keyword in title_lower:
                return True

        # Check for excessive punctuation
        if title.count('！') > 2 or title.count('?') > 2:
            return True

        # Check for all caps
        if title.isupper() and len(title) > 10:
            return True

        return False

    def _detect_sensitive_content(self, content: str) -> bool:
        """Detect potentially sensitive content"""
        if not content:
            return False

        # Simple keyword-based detection
        sensitive_keywords = [
            '政治', '敏感', '审查', '封锁', '抗议', '示威',
            '政府', '领导人', '政策', '法律', '法规',
            '违法', '犯罪', '暴力', '恐怖', '极端'
        ]

        content_lower = content.lower()
        keyword_count = sum(1 for keyword in sensitive_keywords if keyword in content_lower)

        # Flag if multiple sensitive keywords found
        return keyword_count >= 2