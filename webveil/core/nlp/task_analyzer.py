"""
Local Task NLP Analyzer.
Parses natural language user prompts locally before remote LLM egress,
producing a structured TaskRepresentation.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from webveil.core.models.schema import TaskRepresentation

logger = logging.getLogger("WebVeilTaskAnalyzer")


class TaskAnalyzer:
    """
    On-device NLP analyzer converting task prompts into structured TaskRepresentation.
    Runs 100% locally in zero network latency.
    """

    def analyze_task(self, prompt: str) -> TaskRepresentation:
        text = prompt.strip()
        lower = text.lower()

        intent = "general_task"
        entities: List[str] = []
        constraints: Dict[str, Any] = {}
        count: Optional[int] = None
        objective: Optional[str] = None
        actions: List[str] = []

        # 1. Intent Detection
        if any(w in lower for w in ["laptop", "buy", "product", "price", "cheapest", "cost", "amazon", "shop"]):
            intent = "product_search"
            actions.extend(["search", "filter", "compare"])
        elif any(w in lower for w in ["fill", "kyc", "form", "submit", "register", "signup"]):
            intent = "form_fill"
            actions.extend(["inspect_fields", "fill_vault", "submit"])
        elif any(w in lower for w in ["find", "search", "wikipedia", "what", "when", "who", "where", "summarize"]):
            intent = "information_retrieval"
            actions.extend(["search", "extract", "summarize"])

        # 2. Entity Extraction
        entity_keywords = ["laptop", "phone", "tv", "camera", "aadhaar", "email", "password", "isro", "chandrayaan"]
        for ek in entity_keywords:
            if ek in lower:
                entities.append(ek)

        # 3. Numeric & Price Constraint Extraction (e.g., "under 80000", "under ₹80k", "16GB RAM")
        price_match = re.search(r'(?:under|below|max|less than|<)\s*₹?\s*(\d+)(?:k|000)?', lower)
        if price_match:
            val_str = price_match.group(1)
            val = int(val_str) * 1000 if 'k' in lower[price_match.start():price_match.end()+2] or len(val_str) <= 3 else int(val_str)
            constraints["price_max"] = val

        ram_match = re.search(r'(\d+\s*gb)\s*ram', lower)
        if ram_match:
            constraints["ram"] = ram_match.group(1).upper().replace(" ", "")

        # 4. Count Target Extraction (e.g. "three laptops", "3 laptops", "top 5")
        count_match = re.search(r'\b(one|two|three|four|five|1|2|3|4|5)\b(?:\s+options|\s+laptops|\s+items|\s+results)?', lower)
        if count_match:
            num_map = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            c_str = count_match.group(1)
            count = num_map.get(c_str, int(c_str) if c_str.isdigit() else None)

        # 5. Objective Extraction
        if "cheapest" in lower or "lowest price" in lower or "minimum price" in lower:
            objective = "minimum_price"
        elif "highest rating" in lower or "best rated" in lower:
            objective = "maximum_rating"
        elif "summarize" in lower or "summary" in lower:
            objective = "summarization"

        task_rep = TaskRepresentation(
            raw_prompt=prompt,
            intent=intent,
            entities=entities,
            constraints=constraints,
            count=count,
            objective=objective,
            actions=actions,
            confidence=0.96 if intent != "general_task" else 0.80,
        )

        logger.info(
            f"[TaskAnalyzer] Intent: '{task_rep.intent}' | "
            f"Entities: {task_rep.entities} | Constraints: {task_rep.constraints} | "
            f"Objective: {task_rep.objective}"
        )
        return task_rep
