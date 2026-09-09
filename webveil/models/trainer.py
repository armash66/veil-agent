"""
Specialized Model Fine-Tuning & Training Exporter.
Exports Phase 5 browser-agent datasets into standard SFT (Alpaca, ChatML)
and DPO (Direct Preference Optimization) training corpora with action-loss masking.
"""

import json
import logging
from typing import List, Dict, Any
from webveil.datasets.schema import DatasetSample

logger = logging.getLogger("WebVeilModels.Trainer")


class DatasetFineTuningExporter:
    """
    Formats multi-modal browser datasets for supervised fine-tuning (SFT)
    and reinforcement learning from human/rule feedback (DPO/PPO).
    """

    @staticmethod
    def export_alpaca_format(samples: List[DatasetSample], filepath: str):
        """
        Export samples in Alpaca instruction format:
        { "instruction": ..., "input": ..., "output": ... }
        """
        records = []
        for s in samples:
            dom_text = "\n".join([
                f"[{n.node_id}] <{n.tag_name} type='{n.element_type}'>{n.text_content}</{n.tag_name}>"
                for n in s.dom_snapshot if n.is_interactive
            ])
            output_plan = {
                "thought": f"Execute required action for domain '{s.domain}'",
                "actions": [
                    {"action": a.action.value, "node_id": a.node_id, "text": a.text, "thought": a.thought}
                    for a in s.ground_truth_actions
                ]
            }
            records.append({
                "instruction": s.instruction,
                "input": f"URL: {s.initial_url}\nObservation:\n{dom_text}",
                "output": json.dumps(output_plan, indent=2),
            })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        logger.info(f"Exported {len(records)} Alpaca SFT samples to {filepath}")

    @staticmethod
    def export_chatml_format(samples: List[DatasetSample], filepath: str):
        """
        Export samples in OpenAI / ChatML conversation JSONL format:
        {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
        """
        with open(filepath, "w", encoding="utf-8") as f:
            for s in samples:
                dom_text = "\n".join([
                    f"[{n.node_id}] <{n.tag_name}>{n.text_content}</{n.tag_name}>"
                    for n in s.dom_snapshot if n.is_interactive
                ])
                output_plan = {
                    "thought": f"Plan for {s.domain}",
                    "actions": [
                        {"action": a.action.value, "node_id": a.node_id, "text": a.text}
                        for a in s.ground_truth_actions
                    ]
                }
                record = {
                    "messages": [
                        {"role": "system", "content": "You are WebVeil, a privacy-preserving browser agent."},
                        {"role": "user", "content": f"Task: {s.instruction}\nURL: {s.initial_url}\nDOM:\n{dom_text}"},
                        {"role": "assistant", "content": json.dumps(output_plan)},
                    ]
                }
                f.write(json.dumps(record) + "\n")
        logger.info(f"Exported {len(samples)} ChatML SFT samples to {filepath}")

    @staticmethod
    def export_dpo_pairs(samples: List[DatasetSample], filepath: str):
        """
        Export Direct Preference Optimization (DPO) preference pairs:
        {"prompt": ..., "chosen": ..., "rejected": ...}
        Chosen is the ground-truth action; rejected is an arbitrary or non-interactive action.
        """
        records = []
        for s in samples:
            if not s.ground_truth_actions:
                continue

            chosen_plan = json.dumps({
                "thought": "Direct targeted action",
                "actions": [{"action": a.action.value, "node_id": a.node_id, "text": a.text} for a in s.ground_truth_actions]
            })

            # Formulate rejected non-optimal candidate
            rejected_plan = json.dumps({
                "thought": "Irrelevant exploration",
                "actions": [{"action": "wait", "node_id": None, "text": None}]
            })

            records.append({
                "prompt": f"Task: {s.instruction}\nURL: {s.initial_url}",
                "chosen": chosen_plan,
                "rejected": rejected_plan,
                "domain": s.domain,
            })

        with open(filepath, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        logger.info(f"Exported {len(records)} DPO pairs to {filepath}")
