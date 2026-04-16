"""
Internal schemas for source adapters and data pipeline
"""

from .source import (
    SourceType,
    SourceItem,
    FetchResult,
    FetchError,
)
from .content import (
    ContentType,
    QualityLevel,
    ContentMetadata,
    ContentClassification,
    QualityScore,
    ContentProcessingResult,
)

__all__ = [
    "SourceType",
    "SourceItem",
    "FetchResult",
    "FetchError",
    "ContentType",
    "QualityLevel",
    "ContentMetadata",
    "ContentClassification",
    "QualityScore",
    "ContentProcessingResult",
]
