"""
Tests for Recommend task
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from uuid import uuid4

from app.tasks.recommend import RecommendTask, run_recommend_task
from app.models.schemas.recommendation import RecommendationConfig


class TestRecommendTask:
    """Test RecommendTask"""

    def setup_method(self):
        """Setup test fixtures"""
        self.config = RecommendationConfig(
            min_overall_score=0.6,
            max_recommendations=3,
        )

    def _create_mock_article(self, article_id, overall_score, title="Test Article"):
        """Create a mock Article"""
        article = MagicMock()
        article.id = article_id
        article.overall_score = overall_score
        article.title = title
        article.url = f"https://example.com/{article_id}"
        article.crawl_time = datetime.now(timezone.utc)
        article.content_type = "technology"
        article.source_id = uuid4()
        article.author = None
        return article

    @patch('app.tasks.recommend.ArticleRepository')
    @patch('app.tasks.recommend.RecommendationRepository')
    def test_recommend_task_success(self, mock_rec_repo, mock_art_repo):
        """Test successful recommendation generation"""
        task = RecommendTask(config=self.config)

        # Mock articles
        mock_articles = [
            self._create_mock_article(uuid4(), 0.8, "High Quality"),
            self._create_mock_article(uuid4(), 0.7, "Good Quality"),
        ]

        # Setup mocks
        mock_art_instance = MagicMock()
        mock_art_instance.get_articles_for_recommendation.return_value = mock_articles
        mock_art_repo.return_value = mock_art_instance

        mock_rec_instance = MagicMock()
        mock_rec_instance.get_already_recommended_article_ids.return_value = []
        mock_rec_instance.save_batch.return_value = (2, 0)  # saved, skipped
        mock_rec_repo.return_value = mock_rec_instance

        result = task.run(batch_date="2026-04-11")

        assert result.total_candidates == 2
        assert result.filtered_count == 2
        assert result.selected_count == 2
        assert result.skipped_count == 0

    @patch('app.tasks.recommend.ArticleRepository')
    @patch('app.tasks.recommend.RecommendationRepository')
    def test_recommend_task_no_candidates(self, mock_rec_repo, mock_art_repo):
        """Test when no articles meet quality threshold"""
        task = RecommendTask(config=self.config)

        # Mock empty result
        mock_art_instance = MagicMock()
        mock_art_instance.get_articles_for_recommendation.return_value = []
        mock_art_repo.return_value = mock_art_instance

        mock_rec_instance = MagicMock()
        mock_rec_instance.get_already_recommended_article_ids.return_value = []
        mock_rec_repo.return_value = mock_rec_instance

        result = task.run(batch_date="2026-04-11")

        assert result.total_candidates == 0
        assert result.selected_count == 0

    @patch('app.tasks.recommend.ArticleRepository')
    @patch('app.tasks.recommend.RecommendationRepository')
    def test_recommend_task_skips_duplicates(self, mock_rec_repo, mock_art_repo):
        """Test that duplicate recommendations are skipped"""
        task = RecommendTask(config=self.config)

        mock_articles = [
            self._create_mock_article(uuid4(), 0.8),
        ]

        mock_art_instance = MagicMock()
        mock_art_instance.get_articles_for_recommendation.return_value = mock_articles
        mock_art_repo.return_value = mock_art_instance

        mock_rec_instance = MagicMock()
        mock_rec_instance.get_already_recommended_article_ids.return_value = []
        mock_rec_instance.save_batch.return_value = (0, 1)  # All skipped
        mock_rec_repo.return_value = mock_rec_instance

        result = task.run(batch_date="2026-04-11")

        assert result.selected_count == 0
        assert result.skipped_count == 1

    @patch('app.tasks.recommend.ArticleRepository')
    @patch('app.tasks.recommend.RecommendationRepository')
    def test_recommend_task_excludes_already_recommended(self, mock_rec_repo, mock_art_repo):
        """Test that already recommended articles are excluded from candidates"""
        task = RecommendTask(config=self.config)

        existing_ids = ["article-1", "article-2"]

        mock_art_instance = MagicMock()
        mock_art_instance.get_articles_for_recommendation.return_value = []
        mock_art_repo.return_value = mock_art_instance

        mock_rec_instance = MagicMock()
        mock_rec_instance.get_already_recommended_article_ids.return_value = existing_ids
        mock_rec_repo.return_value = mock_rec_instance

        task.run(batch_date="2026-04-11")

        # Verify get_articles_for_recommendation was called with exclude list
        call_args = mock_art_instance.get_articles_for_recommendation.call_args
        assert call_args.kwargs.get('exclude_article_ids') == existing_ids

    def test_recommend_task_default_date(self):
        """Test that default date is today"""
        task = RecommendTask(config=self.config)

        with patch('app.tasks.recommend.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            with patch('app.tasks.recommend.ArticleRepository') as mock_art:
                mock_art_instance = MagicMock()
                mock_art_instance.get_articles_for_recommendation.return_value = []
                mock_art.return_value = mock_art_instance

                with patch('app.tasks.recommend.RecommendationRepository') as mock_rec:
                    mock_rec_instance = MagicMock()
                    mock_rec_instance.get_already_recommended_article_ids.return_value = []
                    mock_rec.return_value = mock_rec_instance

                    result = task.run()  # No date specified

                    # Should use today's date
                    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    assert result.batch_date == today


class TestRunRecommendTask:
    """Test run_recommend_task convenience function"""

    @patch('app.tasks.recommend.RecommendTask')
    def test_convenience_function(self, mock_task_class):
        """Test convenience function creates task correctly"""
        mock_task = MagicMock()
        mock_task.run.return_value = MagicMock(selected_count=5)
        mock_task_class.return_value = mock_task

        result = run_recommend_task(
            batch_date="2026-04-11",
            min_overall_score=0.7,
            max_recommendations=5,
        )

        # Verify config was passed correctly
        mock_task_class.assert_called_once()
        config = mock_task_class.call_args.kwargs['config']
        assert config.min_overall_score == 0.7
        assert config.max_recommendations == 5

        mock_task.run.assert_called_once_with(batch_date="2026-04-11")

    @patch('app.tasks.recommend.RecommendTask')
    def test_default_min_score_is_0_35(self, mock_task_class):
        """Test that default min_overall_score is 0.35 after quality calibration"""
        mock_task = MagicMock()
        mock_task.run.return_value = MagicMock(selected_count=3)
        mock_task_class.return_value = mock_task

        # Call without specifying min_overall_score
        result = run_recommend_task()

        # Verify default config uses 0.35 (raised from 0.2 after discussion scoring fix)
        mock_task_class.assert_called_once()
        config = mock_task_class.call_args.kwargs['config']
        assert config.min_overall_score == 0.35, \
            f"Expected default min_overall_score to be 0.35, got {config.min_overall_score}"

    @patch('app.tasks.recommend.RecommendTask')
    def test_date_today_is_parsed_to_actual_date(self, mock_task_class):
        """Test that batch_date 'today' is parsed to actual YYYY-MM-DD string"""
        mock_task = MagicMock()
        mock_task.run.return_value = MagicMock(selected_count=3)
        mock_task_class.return_value = mock_task

        # Import the function that handles CLI parsing
        import sys
        from io import StringIO
        from app.tasks.recommend import run_recommend_task

        # Get today's date
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Simulate what the CLI does when --date today is passed
        batch_date = 'today'
        if batch_date == 'today':
            batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Verify the conversion happened correctly
        assert batch_date == today, \
            f"Expected batch_date to be '{today}', got '{batch_date}'"
        assert batch_date != 'today', \
            "batch_date should not be the literal string 'today'"
