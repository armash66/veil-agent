"""
WebVeil Browser-Agent Dataset Subsystem.
Provides dataset schemas, curated SIH benchmark task generation,
and train/validation/test dataset loaders.
"""

from webveil.datasets.schema import DatasetSample, DatasetSplit
from webveil.datasets.builder import DatasetBuilder
from webveil.datasets.loader import DatasetLoader

__all__ = [
    "DatasetSample",
    "DatasetSplit",
    "DatasetBuilder",
    "DatasetLoader",
]
