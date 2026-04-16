"""
Fetch task - Main entry point for content ingestion

This module provides the core fetch task that:
1. Calls source adapters to fetch content items
2. Stores items in the database via repositories
3. Handles errors and provides statistics
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from app.core.database import get_db, get_engine
from app.core.logging import get_logger
from app.models.schemas.source import SourceItem, FetchResult, FetchError
from app.models.schemas.content import ContentClassification, QualityScore
from app.services.sources.base import SourceAdapter
from app.services.intelligence.classifier import ContentClassifier
from app.services.intelligence.quality import ContentQualityScorer
from app.repositories.article_repository import ArticleRepository

logger = get_logger(__name__)


class FetchTask:
    """
    Main fetch task orchestrator

    Coordinates between source adapters and repositories to ingest content.
    """

    def __init__(self, adapter: SourceAdapter, enable_classification: bool = True, enable_quality_scoring: bool = True):
        """
        Initialize fetch task with a source adapter

        Args:
            adapter: SourceAdapter instance
            enable_classification: Whether to enable content classification
            enable_quality_scoring: Whether to enable quality scoring
        """
        self.adapter = adapter
        self.source_name = adapter.source_name
        self.enable_classification = enable_classification
        self.enable_quality_scoring = enable_quality_scoring
        self.classifier = ContentClassifier() if enable_classification else None
        self.quality_scorer = ContentQualityScorer() if enable_quality_scoring else None

    def run(self, limit: int = 10, fetch_full_content: bool = False) -> FetchResult:
        """
        Execute the fetch task

        Args:
            limit: Maximum number of items to fetch
            fetch_full_content: Whether to fetch full content for each item

        Returns:
            FetchResult with statistics and errors
        """
        start_time = datetime.now(timezone.utc)
        result = FetchResult(
            source_name=self.source_name,
            success=False,
            started_at=start_time,
        )

        logger.info(f"Starting fetch task for {self.source_name}, limit={limit}")

        try:
            # Step 1: Fetch items from source
            fetch_result = self.adapter.fetch_items(limit=limit)

            if not fetch_result.success:
                logger.error(f"Failed to fetch from {self.source_name}")
                result.add_error(f"Fetch failed: {', '.join(fetch_result.errors)}")
                return self._finalize_result(result, start_time, success=False)

            items = self._extract_items(fetch_result)
            result.items_fetched = len(items)

            if not items:
                logger.info(f"No items fetched from {self.source_name}")
                return self._finalize_result(result, start_time, success=True)

            # Step 2: Store items in database
            with get_db() as db:
                repo = ArticleRepository(db)

                # Get or create source
                source = self._get_or_create_source(repo)

                for item in items:
                    try:
                        # Step 2a: Get or create author
                        author_id = self._get_or_create_author(repo, source, item)

                        # Step 2b: Fetch full content if requested
                        original_content = None
                        if fetch_full_content:
                            original_content = self._fetch_item_content(item)

                        # Step 2c: Classify content if enabled
                        classification = None
                        if self.classifier:
                            try:
                                # Use original_content if available, fallback to summary
                                content_for_classification = original_content or item.summary or ""
                                classification_result = self.classifier.classify(
                                    source_item=item,
                                    content=content_for_classification
                                )
                                classification = self._classification_to_dict(classification_result)
                                logger.debug(f"Classified {item.source_item_id} as {classification_result.content_type.value}")
                            except Exception as e:
                                logger.warning(f"Classification failed for {item.source_item_id}: {e}")

                        # Step 2d: Score quality if enabled
                        quality = None
                        if self.quality_scorer:
                            try:
                                # Use original_content if available, fallback to summary
                                content_for_scoring = original_content or item.summary or ""
                                quality_result = self.quality_scorer.score(
                                    source_item=item,
                                    content=content_for_scoring
                                )
                                quality = self._quality_to_dict(quality_result)
                                logger.debug(f"Scored {item.source_item_id} with overall_score={quality_result.overall_score:.3f}")
                            except Exception as e:
                                logger.warning(f"Quality scoring failed for {item.source_item_id}: {e}")

                        # Step 2e: Upsert article with classification and quality data
                        _, is_new = repo.upsert_article(
                            item=item,
                            source_id=str(source.id),
                            author_id=author_id,
                            original_content=original_content,
                            classification=classification,
                            quality=quality,
                        )

                        if is_new:
                            result.items_new += 1
                        else:
                            result.items_updated += 1

                    except Exception as e:
                        error = self.adapter.handle_error(e, item.source_item_id)
                        result.add_error(f"Item {item.source_item_id}: {error.message}")
                        self.adapter.log_error(error)

            return self._finalize_result(result, start_time, success=True)

        except Exception as e:
            logger.exception(f"Fatal error in fetch task for {self.source_name}")
            error = self.adapter.handle_error(e)
            result.add_error(f"Task failed: {error.message}")
            return self._finalize_result(result, start_time, success=False)

    def _extract_items(self, fetch_result: FetchResult) -> List[SourceItem]:
        """
        Extract items from fetch result

        Args:
            fetch_result: Result from adapter.fetch_items()

        Returns:
            List of SourceItem instances
        """
        # Our adapter returns items directly in fetch_result
        if hasattr(fetch_result, 'items') and fetch_result.items:
            return fetch_result.items
        return []

    def _get_or_create_source(self, repo: ArticleRepository):
        """Get or create source in database"""
        from urllib.parse import urlparse

        parsed_url = urlparse(self.adapter.base_url)
        domain = parsed_url.netloc
        source_key = f"{self.adapter.source_name}_{domain}"

        return repo.get_or_create_source(
            name=self.adapter.source_name,
            domain=domain,
            source_type=self.adapter.source_type,
            base_url=self.adapter.base_url,
            source_key=source_key,
            slug=self.adapter.source_name,
        )

    def _get_or_create_author(
        self,
        repo: ArticleRepository,
        source,
        item: SourceItem,
    ) -> Optional[str]:
        """Get or create author, return author ID or None"""
        if not item.author_name and not item.author_url:
            return None

        author = repo.get_or_create_author(
            source_id=str(source.id),
            username=item.author_name,  # Use author_name as username for simplicity
            name=item.author_name,
            author_url=item.author_url,
        )
        return str(author.id) if author else None

    def _fetch_item_content(self, item: SourceItem) -> Optional[str]:
        """
        Fetch full content for an item

        Args:
            item: SourceItem to fetch content for

        Returns:
            Full content string or None if fetch fails
        """
        try:
            return self.adapter.fetch_full_content(item)
        except Exception as e:
            error = self.adapter.handle_error(e, item.source_item_id)
            self.adapter.log_error(error)
            return None

    def _classification_to_dict(self, classification: ContentClassification) -> dict:
        """Convert ContentClassification to dict for repository"""
        return {
            'content_type': classification.content_type.value,
            'confidence': classification.confidence,
            'tags': classification.tags,
            'subcategories': classification.subcategories,
        }

    def _quality_to_dict(self, quality: QualityScore) -> dict:
        """Convert QualityScore to dict for repository"""
        return {
            'overall_score': quality.overall_score,
            'quality_level': quality.quality_level.value,
            'completeness_score': quality.completeness_score,
            'structure_score': quality.structure_score,
            'depth_score': quality.depth_score,
            'credibility_score': quality.credibility_score,
            'engagement_score': quality.engagement_score,
            'is_original': quality.is_original,
            'has_citation': quality.has_citation,
            'is_clickbait': quality.is_clickbait,
        }

    def _finalize_result(
        self,
        result: FetchResult,
        start_time: datetime,
        success: bool,
    ) -> FetchResult:
        """Finalize and return the fetch result"""
        result.success = success
        result.finished_at = datetime.now(timezone.utc)
        result.duration_seconds = (result.finished_at - start_time).total_seconds()

        logger.info(
            f"Fetch task completed for {self.source_name}: "
            f"success={result.success}, "
            f"fetched={result.items_fetched}, "
            f"new={result.items_new}, "
            f"updated={result.items_updated}, "
            f"failed={result.items_failed}, "
            f"duration={result.duration_seconds:.2f}s"
        )

        return result


if __name__ == '__main__':
    # Command-line entry point for fetch task
    import argparse
    import sys

    from app.services.sources.v2ex import V2EXAdapter
    from app.services.sources.solidot import SolidotAdapter

    parser = argparse.ArgumentParser(description='Fetch content from sources')
    parser.add_argument(
        '--source',
        type=str,
        default='v2ex',
        help='Source to fetch from (default: v2ex, options: v2ex, solidot)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum items to fetch (default: 10)'
    )
    parser.add_argument(
        '--mode',
        type=str,
        default='latest',
        help='Fetch mode: latest or hot (default: latest, only for v2ex)'
    )
    parser.add_argument(
        '--no-classification',
        action='store_true',
        help='Disable content classification'
    )
    parser.add_argument(
        '--no-quality',
        action='store_true',
        help='Disable quality scoring'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    # Validate source and create adapter
    supported_sources = ['v2ex', 'solidot']
    if args.source not in supported_sources:
        print(f"Error: Unsupported source '{args.source}'. Supported: {', '.join(supported_sources)}", file=sys.stderr)
        sys.exit(1)

    # Create adapter based on source
    if args.source == 'v2ex':
        adapter = V2EXAdapter(config={'mode': args.mode})
    elif args.source == 'solidot':
        adapter = SolidotAdapter(config={})

    # Create and run task
    task = FetchTask(
        adapter=adapter,
        enable_classification=not args.no_classification,
        enable_quality_scoring=not args.no_quality,
    )

    print(f"Fetching from {args.source} (mode={args.mode}, limit={args.limit})...")
    result = task.run(limit=args.limit)

    print(f"\nFetch Results")
    print(f"{'=' * 50}")
    print(f"Source: {result.source_name}")
    print(f"Success: {result.success}")
    print(f"Items Fetched: {result.items_fetched}")
    print(f"Items New: {result.items_new}")
    print(f"Items Updated: {result.items_updated}")
    print(f"Items Failed: {result.items_failed}")
    print(f"Duration: {result.duration_seconds:.2f}s")

    if result.errors:
        print(f"\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    if args.verbose and result.items:
        print(f"\nFetched Items:")
        for item in result.items[:5]:
            print(f"  - [{item.source_item_id}] {item.title[:50]}...")

    sys.exit(0 if result.success else 1)


def run_fetch_task(
    adapter: SourceAdapter,
    limit: int = 10,
    test_mode: bool = False,
    enable_classification: bool = True,
    enable_quality_scoring: bool = True,
) -> FetchResult:
    """
    Convenience function to run a fetch task

    Args:
        adapter: SourceAdapter instance
        limit: Maximum number of items to fetch
        test_mode: If True, return items with the result for testing
        enable_classification: Whether to enable content classification
        enable_quality_scoring: Whether to enable quality scoring

    Returns:
        FetchResult with statistics
    """
    task = FetchTask(
        adapter=adapter,
        enable_classification=enable_classification,
        enable_quality_scoring=enable_quality_scoring,
    )
    result = task.run(limit=limit)

    # For testing, we add items to the result
    if test_mode and hasattr(adapter, '_last_items'):
        result.items = adapter._last_items

    return result
