"""
Dataset Schemas for Browser-Agent Evaluation and Training.
Defines typed sample representations with multi-modal observations,
ground-truth action plans, and privacy annotations.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from webveil.core.models.schema import DOMNode, BrowserAction, ActionType, TextRegion, PIIMatch, PIICategory


@dataclass
class DatasetSample:
    """
    A single browser-agent benchmark or training instance.
    Includes prompt, observation state, annotated PII, and ground-truth action trajectory.
    """
    sample_id: str
    domain: str  # "ecommerce", "banking", "aws_console", "travel", "government", "adversarial"
    instruction: str
    initial_url: str
    dom_snapshot: List[DOMNode] = field(default_factory=list)
    a11y_tree: Optional[Dict[str, Any]] = None
    ocr_regions: List[TextRegion] = field(default_factory=list)
    ground_truth_actions: List[BrowserAction] = field(default_factory=list)
    ground_truth_pii: List[PIIMatch] = field(default_factory=list)
    expected_target_node_id: Optional[int] = None
    difficulty: str = "medium"  # "easy", "medium", "hard", "adversarial"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert sample to JSON-serializable dictionary."""
        return {
            "sample_id": self.sample_id,
            "domain": self.domain,
            "instruction": self.instruction,
            "initial_url": self.initial_url,
            "dom_snapshot": [
                {
                    "node_id": n.node_id,
                    "tag_name": n.tag_name,
                    "element_type": n.element_type,
                    "name": n.name,
                    "text_content": n.text_content,
                    "value": n.value,
                    "is_interactive": n.is_interactive,
                    "is_visible": n.is_visible,
                    "bounding_box": n.bounding_box,
                    "attributes": n.attributes,
                }
                for n in self.dom_snapshot
            ],
            "a11y_tree": self.a11y_tree,
            "ocr_regions": [
                {
                    "text": r.text,
                    "bounding_box": r.bounding_box,
                    "confidence": r.confidence,
                    "source": r.source,
                }
                for r in self.ocr_regions
            ],
            "ground_truth_actions": [
                {
                    "action": a.action.value,
                    "node_id": a.node_id,
                    "text": a.text,
                    "thought": a.thought,
                }
                for a in self.ground_truth_actions
            ],
            "ground_truth_pii": [
                {
                    "category": p.category.name,
                    "raw_value": p.raw_value,
                    "placeholder": p.placeholder,
                    "source_node_id": p.source_node_id,
                    "bounding_box": p.bounding_box,
                }
                for p in self.ground_truth_pii
            ],
            "expected_target_node_id": self.expected_target_node_id,
            "difficulty": self.difficulty,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetSample":
        """Reconstruct DatasetSample from dictionary."""
        dom_nodes = [
            DOMNode(
                node_id=nd["node_id"],
                tag_name=nd["tag_name"],
                element_type=nd.get("element_type"),
                name=nd.get("name"),
                text_content=nd.get("text_content", ""),
                value=nd.get("value", ""),
                is_interactive=nd.get("is_interactive", False),
                is_visible=nd.get("is_visible", True),
                bounding_box=nd.get("bounding_box"),
                attributes=nd.get("attributes", {}),
            )
            for nd in data.get("dom_snapshot", [])
        ]

        ocr_regions = [
            TextRegion(
                text=rd["text"],
                bounding_box=rd["bounding_box"],
                confidence=rd.get("confidence", 0.0),
                source=rd.get("source", "ocr"),
            )
            for rd in data.get("ocr_regions", [])
        ]

        actions = [
            BrowserAction(
                action=ActionType(ad["action"]),
                node_id=ad.get("node_id"),
                text=ad.get("text"),
                thought=ad.get("thought", ""),
            )
            for ad in data.get("ground_truth_actions", [])
        ]

        pii_matches = [
            PIIMatch(
                category=PIICategory[pd["category"]],
                raw_value=pd["raw_value"],
                placeholder=pd["placeholder"],
                source_node_id=pd.get("source_node_id"),
                bounding_box=pd.get("bounding_box"),
            )
            for pd in data.get("ground_truth_pii", [])
        ]

        return cls(
            sample_id=data["sample_id"],
            domain=data["domain"],
            instruction=data["instruction"],
            initial_url=data["initial_url"],
            dom_snapshot=dom_nodes,
            a11y_tree=data.get("a11y_tree"),
            ocr_regions=ocr_regions,
            ground_truth_actions=actions,
            ground_truth_pii=pii_matches,
            expected_target_node_id=data.get("expected_target_node_id"),
            difficulty=data.get("difficulty", "medium"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DatasetSplit:
    """Train, validation, and test dataset splits."""
    train: List[DatasetSample] = field(default_factory=list)
    val: List[DatasetSample] = field(default_factory=list)
    test: List[DatasetSample] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        """Summary metrics across all splits."""
        return {
            "train_count": len(self.train),
            "val_count": len(self.val),
            "test_count": len(self.test),
            "total_count": len(self.train) + len(self.val) + len(self.test),
        }
