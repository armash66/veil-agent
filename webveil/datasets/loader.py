"""
Dataset Loader and Split Generator.
Handles dataset loading, filtering, splitting, and format conversion
for evaluation benchmarks and model fine-tuning.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from webveil.datasets.schema import DatasetSample, DatasetSplit

logger = logging.getLogger("WebVeilDatasets.Loader")


class DatasetLoader:
    """
    Manages loading, partitioning, and formatting browser-agent datasets.
    """

    @staticmethod
    def split_dataset(
        samples: List[DatasetSample],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
    ) -> DatasetSplit:
        """
        Split sample list into deterministic train, val, and test subsets.
        """
        if not samples:
            return DatasetSplit()

        n = len(samples)
        train_end = max(1, int(n * train_ratio))
        val_end = max(train_end + 1, int(n * (train_ratio + val_ratio))) if n > 2 else train_end

        train_samples = samples[:train_end]
        val_samples = samples[train_end:val_end]
        test_samples = samples[val_end:]

        # Guarantee at least 1 in val and test if n >= 3
        if n >= 3 and not test_samples:
            test_samples = [val_samples.pop()]

        return DatasetSplit(
            train=train_samples,
            val=val_samples,
            test=test_samples,
        )

    @staticmethod
    def filter_by_domain(samples: List[DatasetSample], domain: str) -> List[DatasetSample]:
        """Filter dataset samples matching domain."""
        return [s for s in samples if s.domain.lower() == domain.lower()]

    @staticmethod
    def filter_by_difficulty(samples: List[DatasetSample], difficulty: str) -> List[DatasetSample]:
        """Filter dataset samples matching difficulty."""
        return [s for s in samples if s.difficulty.lower() == difficulty.lower()]

    @staticmethod
    def filter_pii_tasks(samples: List[DatasetSample]) -> List[DatasetSample]:
        """Filter dataset samples that contain ground-truth PII."""
        return [s for s in samples if len(s.ground_truth_pii) > 0]

    @staticmethod
    def save_jsonl(samples: List[DatasetSample], filepath: str):
        """Serialize dataset samples into JSON Lines file."""
        with open(filepath, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s.to_dict()) + "\n")

    @staticmethod
    def load_jsonl(filepath: str) -> List[DatasetSample]:
        """Load dataset samples from JSON Lines file."""
        samples: List[DatasetSample] = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    samples.append(DatasetSample.from_dict(d))
        return samples

    @staticmethod
    def to_fine_tuning_pairs(samples: List[DatasetSample]) -> List[Dict[str, Any]]:
        """
        Convert dataset samples into instruction-tuning prompt/response pairs
        for specialized model training (Phase 6).
        """
        pairs = []
        for s in samples:
            dom_text = "\n".join([
                f"[{n.node_id}] <{n.tag_name}> {n.text_content}"
                for n in s.dom_snapshot if n.is_interactive
            ])
            actions_text = "\n".join([
                f"Action: {a.action.value} node_id={a.node_id} text='{a.text or ''}' # {a.thought}"
                for a in s.ground_truth_actions
            ])

            pairs.append({
                "prompt": f"Task: {s.instruction}\nURL: {s.initial_url}\nObservation:\n{dom_text}",
                "completion": actions_text,
                "metadata": {
                    "sample_id": s.sample_id,
                    "domain": s.domain,
                    "difficulty": s.difficulty,
                }
            })
        return pairs
