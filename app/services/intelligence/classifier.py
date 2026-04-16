"""
Content Classifier

Rule-based content classification for Chinese content.
"""

import logging
import re
from typing import List, Dict, Set, Optional
from collections import Counter

from app.models.schemas.content import (
    ContentType,
    ContentClassification,
    ContentMetadata,
    SourceItem,
)

logger = logging.getLogger(__name__)


class ContentClassifier:
    """
    Rule-based content classifier for Chinese content

    Classifies content into predefined categories based on:
    - Keywords in title and content
    - Content structure
    - Source characteristics
    - Author information
    """

    def __init__(self):
        """Initialize classifier with predefined rules"""
        # Define keyword patterns for each content type
        self._define_type_keywords()
        # Define source-specific patterns
        self._define_source_patterns()
        # Define author patterns
        self._define_author_patterns()

    def classify(self,
                 source_item: SourceItem,
                 content: str = "",
                 metadata: Optional[ContentMetadata] = None) -> ContentClassification:
        """
        Classify content based on rules

        Args:
            source_item: The source content item
            content: Full content text (if available)
            metadata: Content metadata (if available)

        Returns:
            ContentClassification with type, confidence, and tags
        """
        classification = ContentClassification()

        # Check for empty content - short circuit to UNKNOWN
        title = (source_item.title or "").strip()
        summary = (source_item.summary or "").strip()
        content_stripped = (content or "").strip()

        if not title and not summary and not content_stripped:
            classification.content_type = ContentType.UNKNOWN
            classification.confidence = 0.0
            return classification

        # Extract features from different sources
        title_features = self._extract_text_features(source_item.title or "")
        summary_features = self._extract_text_features(source_item.summary or "")
        content_features = self._extract_text_features(content) if content else {}
        source_features = self._extract_source_features(source_item)
        author_features = self._extract_author_features(source_item)

        # Combine all features
        all_features = {
            **title_features,
            **summary_features,
            **content_features,
            **source_features,
            **author_features,
        }

        # Extract metadata from content if not provided
        if metadata is None and content:
            metadata = self._extract_metadata_from_content(content)

        # Classify based on features
        classification = self._classify_by_rules(all_features, source_item)

        # Set metadata if provided or extracted
        if metadata:
            classification.metadata = metadata

        return classification

    def _define_type_keywords(self):
        """Define keyword patterns for each content type"""
        self.type_keywords = {
            ContentType.TECHNOLOGY: {
                # Programming languages
                '编程', '代码', '开发', '程序员', '工程师', 'programming', 'code', 'developer',
                'python', 'java', 'javascript', 'go', 'rust', 'c++', '算法', '数据结构',
                '框架', 'framework', 'library', 'api', 'sdk',
                # Technology concepts
                '人工智能', 'ai', '机器学习', '深度学习', 'neural', 'blockchain',
                '云计算', 'cloud', 'docker', 'kubernetes', '微服务', '架构',
                '前端', '后端', 'fullstack', 'devops', '测试', 'debug',
            },
            ContentType.PRODUCT: {
                # Product management
                '产品', 'product', 'pm', '需求', '设计', '用户体验', 'ux', 'ui',
                '功能', '迭代', '版本', 'roadmap', 'prd', 'mvp',
                '增长', 'growth', '运营', '运营策略', '用户增长',
                # Business
                '商业模式', 'business model', '市场', '竞争', '战略',
            },
            ContentType.LIFE: {
                # Daily life
                '生活', 'life', '日常', '日记', '随笔', '感悟',
                '美食', 'recipe', 'cooking', '旅行', 'travel', '摄影', 'photo',
                '健身', 'health', '运动', '运动', 'yoga', '冥想',
                '宠物', '宠物', '家庭', 'family', '亲子', 'parenting',
            },
            ContentType.CULTURE: {
                # Books and media
                '读书', '读书笔记', 'book', '读书分享', '书单',
                '电影', 'movie', '影评', 'film', '剧集', 'drama',
                '音乐', 'music', '专辑', 'concert', '演出',
                '艺术', 'art', '展览', 'museum', '文化', 'culture',
            },
            ContentType.DISCUSSION: {
                # Discussion patterns
                '讨论', 'discussion', 'poll', '投票', '大家怎么看',
                '分享', 'share', '交流', '提问', '问题',
                '社区', 'community', '论坛', 'forum', '问答', 'qa',
                '经验', 'experience', '心得', 'thoughts', '看法',
                # Question patterns (high weight for discussion)
                '如何', '怎么', '怎么样', '为什么', '怎么办',
                '怎么看', '如何看待', '怎么选', '怎么用',
                '求助', '请教', '请问', '大家', '听听',
            },
            ContentType.NEWS: {
                # News indicators
                '新闻', 'news', '报道', 'report', '快讯', 'breaking',
                '发布会', 'launch', '发布', '官宣', '声明',
                '行业', 'industry', '动态', 'update', '趋势',
            },
            ContentType.TUTORIAL: {
                # Tutorial patterns
                '教程', 'tutorial', 'guide', 'how to', '教程',
                '手把手', 'step by step', '入门', 'beginner',
                '实践', 'practice', '实战', '案例', 'case study',
                '学习', 'learn', '学习笔记', '笔记',
            },
            ContentType.OPINION: {
                # Opinion indicators
                '观点', 'opinion', '看法', '观点', '思考', 'thinking',
                '分析', 'analysis', '评论', 'review', '批评', 'criticism',
                '我认为', '在我看来', '我的观点', '个人观点',
            },
        }

    def _define_source_patterns(self):
        """Define source-specific patterns"""
        self.source_patterns = {
            'sspai': {
                ContentType.TECHNOLOGY: 0.6,
                ContentType.PRODUCT: 0.3,
                ContentType.TUTORIAL: 0.5,
            },
            'v2ex': {
                ContentType.DISCUSSION: 0.8,
                ContentType.TECHNOLOGY: 0.4,
                ContentType.NEWS: 0.2,
            },
            'zhihu': {
                ContentType.TECHNOLOGY: 0.4,
                ContentType.PRODUCT: 0.3,
                ContentType.DISCUSSION: 0.5,
                ContentType.CULTURE: 0.2,
            },
            'douban': {
                ContentType.CULTURE: 0.8,
                ContentType.LIFE: 0.3,
                ContentType.OPINION: 0.4,
            },
        }

    def _define_author_patterns(self):
        """Define author-specific patterns"""
        self.author_patterns = {
            # Authors known for specific content types
            '工程师': ContentType.TECHNOLOGY,
            '产品经理': ContentType.PRODUCT,
            '设计师': ContentType.PRODUCT,
            '作者': ContentType.CULTURE,
            '作家': ContentType.CULTURE,
            '导演': ContentType.CULTURE,
            '摄影师': ContentType.CULTURE,
            '医生': ContentType.LIFE,
            '律师': ContentType.LIFE,
            '老师': ContentType.TUTORIAL,
        }

    def _extract_text_features(self, text: str) -> Dict[str, int]:
        """Extract keyword features from text"""
        if not text:
            return {}

        # Normalize text
        text = text.lower()

        # Count keywords for each type
        features = {}
        for content_type, keywords in self.type_keywords.items():
            count = sum(1 for keyword in keywords if keyword in text)
            if count > 0:
                features[content_type.value] = count

        # Extract structural features
        features['has_question'] = int('？' in text or '?' in text)
        features['has_exclamation'] = int('！' in text or '!' in text)
        features['has_code_block'] = int('```' in text)
        features['paragraph_count'] = text.count('\n\n') + 1

        return features

    def _extract_source_features(self, source_item: SourceItem) -> Dict[str, int]:
        """Extract source-specific features"""
        features = {}

        # Source-based scoring
        source_id = source_item.source_id
        if source_id in self.source_patterns:
            for content_type, score in self.source_patterns[source_id].items():
                features[f"source_{content_type.value}"] = int(score > 0.5)

        return features

    def _extract_author_features(self, source_item: SourceItem) -> Dict[str, int]:
        """Extract author-specific features"""
        features = {}

        if source_item.author_name:
            # Check for known author patterns
            for author_pattern, content_type in self.author_patterns.items():
                if author_pattern in source_item.author_name:
                    features[f"author_{content_type.value}"] = 1

        return features

    def _classify_by_rules(self, features: Dict[str, int], source_item: SourceItem) -> ContentClassification:
        """Classify content based on extracted features"""
        classification = ContentClassification()

        # Score each content type
        type_scores = {}

        # Define type priorities (higher = more likely to be primary type)
        # Tutorial should have lower priority than topic-based types
        type_priority = {
            ContentType.TECHNOLOGY: 1.2,
            ContentType.PRODUCT: 1.2,
            ContentType.CULTURE: 1.2,
            ContentType.DISCUSSION: 1.1,
            ContentType.NEWS: 1.0,
            ContentType.OPINION: 1.0,
            ContentType.LIFE: 1.0,
            ContentType.TUTORIAL: 0.8,  # Lower priority - often a modifier
        }

        # Calculate text-based scores
        text_types = [t for t in ContentType if t.value in features]
        for content_type in text_types:
            keyword_count = features.get(content_type.value, 0)
            # Use min-max normalization with reasonable max expectation
            # Expecting 3-5 keywords for high confidence
            base_score = min(keyword_count / 3.0, 1.0)
            # Apply type priority
            type_scores[content_type] = base_score * type_priority.get(content_type, 1.0)

        # Add source-based scores (stronger weight)
        source_id = source_item.source_id
        if source_id in self.source_patterns:
            for content_type, base_score in self.source_patterns[source_id].items():
                if content_type in type_scores:
                    type_scores[content_type] += base_score * 0.5  # 50% weight
                else:
                    # Source can also introduce a type
                    type_scores[content_type] = base_score * 0.3

        # Add author-based scores (stronger weight)
        if source_item.author_name:
            for author_pattern, content_type in self.author_patterns.items():
                if author_pattern in source_item.author_name:
                    if content_type in type_scores:
                        type_scores[content_type] += 0.3  # 30% bonus
                    else:
                        type_scores[content_type] = 0.2

        # Boost discussion score for question-based content from discussion sources
        if source_item.source_id in ['v2ex', 'zhihu'] and features.get('has_question'):
            if ContentType.DISCUSSION in type_scores:
                type_scores[ContentType.DISCUSSION] += 0.4
            else:
                type_scores[ContentType.DISCUSSION] = 0.3

        # Determine primary type
        if type_scores:
            # Get type with highest score
            best_type = max(type_scores.items(), key=lambda x: x[1])
            classification.content_type = best_type[0]
            # Normalize confidence to 0-1 range, but ensure minimum for valid classifications
            raw_score = best_type[1]
            classification.confidence = min(max(raw_score, 0.3), 1.0)

            # Add related tags
            self._add_related_tags(classification, source_item)

            # Set subcategories based on content
            self._set_subcategories(classification, features, source_item)

        return classification

    def _add_related_tags(self, classification: ContentClassification, source_item: SourceItem):
        """Add related tags based on classification"""
        tags = []

        # Add content type tag
        tags.append(classification.content_type.value)

        # Add source-based tags
        if source_item.source_id:
            tags.append(f"from_{source_item.source_id}")

        # Add author-based tags if author is notable
        if source_item.author_name:
            author_name = source_item.author_name.lower()
            if '专栏' in author_name or '编辑' in author_name:
                tags.append('official')
            elif '认证' in author_name or '专家' in author_name:
                tags.append('expert')

        classification.tags = tags

    def _set_subcategories(self, classification: ContentClassification,
                          features: Dict[str, int], source_item: SourceItem):
        """Set subcategories based on content features"""
        subcategories = []

        # Technology subcategories
        if classification.content_type == ContentType.TECHNOLOGY:
            if 'python' in source_item.title.lower() or 'python' in (source_item.summary or '').lower():
                subcategories.append('python')
            if '前端' in source_item.title or 'frontend' in source_item.title.lower():
                subcategories.append('frontend')
            if '后端' in source_item.title or 'backend' in source_item.title.lower():
                subcategories.append('backend')
            if 'ai' in source_item.title.lower() or '人工智能' in source_item.title:
                subcategories.append('ai')

        # Product subcategories
        elif classification.content_type == ContentType.PRODUCT:
            if '设计' in source_item.title or 'design' in source_item.title.lower():
                subcategories.append('design')
            if '运营' in source_item.title or 'growth' in source_item.title.lower():
                subcategories.append('growth')

        # Culture subcategories
        elif classification.content_type == ContentType.CULTURE:
            if '读书' in source_item.title or 'book' in source_item.title.lower():
                subcategories.append('books')
            if '电影' in source_item.title or 'movie' in source_item.title.lower():
                subcategories.append('movies')
            if '音乐' in source_item.title or 'music' in source_item.title.lower():
                subcategories.append('music')

        classification.subcategories = subcategories

    def _extract_metadata_from_content(self, content: str) -> ContentMetadata:
        """Extract metadata from content text"""
        metadata = ContentMetadata()

        if content:
            metadata.word_count = len(content)
            # Count non-empty lines as paragraphs (each line is a separate paragraph)
            lines = [line.strip() for line in content.split('\n')]
            non_empty_lines = [line for line in lines if line]
            metadata.paragraph_count = len(non_empty_lines)
            metadata.has_code = '```' in content
            metadata.quote_count = content.count('> ')

        return metadata