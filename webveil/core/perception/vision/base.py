"""
Base Protocol & Data Structures for Browser-Local Vision Perception.
Adheres to the WebVeil principle: Vision runs on the browser/client side,
producing UI structural regions (controls, dialogs, cards, inputs) without uploading raw screenshots.
"""

import time
from dataclasses import dataclass, field
from typing import Protocol, List, Dict, Any, Optional
from PIL import Image

from webveil.core.models.schema import VisualRegion


@dataclass
class VisionModelMetadata:
    """Empirically measured attributes of a local vision model backend."""
    model_name: str
    backend: str  # "browser_webgpu" | "wasm" | "local_cv_lightweight" | "onnx_runtime"
    device: str   # "client_browser" | "cpu" | "gpu"
    memory_footprint_mb: float = 0.0
    inference_latency_ms: float = 0.0
    is_browser_local: bool = True
    parameters_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "backend": self.backend,
            "device": self.device,
            "memory_footprint_mb": round(self.memory_footprint_mb, 2),
            "inference_latency_ms": round(self.inference_latency_ms, 2),
            "is_browser_local": self.is_browser_local,
            "parameters_count": self.parameters_count,
        }


class LocalVisionModel(Protocol):
    """
    Pluggable interface for genuine client-side visual perception models.
    Supports browser WebGPU/Wasm runtimes and local client backends.
    """

    def detect_regions(self, image: Image.Image, viewport: Optional[Dict[str, float]] = None) -> List[VisualRegion]:
        """
        Detect visual UI regions from screenshot image.
        Returns regions mapped to viewport coordinates.
        """
        ...

    def get_metadata(self) -> VisionModelMetadata:
        """Returns dynamically measured model metadata."""
        ...
