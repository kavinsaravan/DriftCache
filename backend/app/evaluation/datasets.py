"""Typed adapters over the canonical JSON evaluation datasets."""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

DATASETS_DIR = Path(__file__).parents[3] / "datasets"


class EquivalenceLabel(str, Enum):
    EQUIVALENT = "equivalent"
    NOT_EQUIVALENT = "not_equivalent"
    PARTIALLY_EQUIVALENT = "partially_equivalent"


@dataclass
class PromptPair:
    prompt_a: str
    prompt_b: str
    label: EquivalenceLabel
    category: str
    notes: str = ""

    def should_cache_hit(self) -> bool:
        return self.label == EquivalenceLabel.EQUIVALENT


class EvaluationDataset:
    def __init__(self, name: str, pairs: List[PromptPair]):
        self.name = name
        self.pairs = pairs

    def __len__(self) -> int:
        return len(self.pairs)

    def get_equivalent_pairs(self) -> List[PromptPair]:
        return [
            pair for pair in self.pairs if pair.label == EquivalenceLabel.EQUIVALENT
        ]

    def get_non_equivalent_pairs(self) -> List[PromptPair]:
        return [
            pair for pair in self.pairs if pair.label == EquivalenceLabel.NOT_EQUIVALENT
        ]

    def summary(self) -> Dict:
        return {
            "name": self.name,
            "total_pairs": len(self.pairs),
            "equivalent": len(self.get_equivalent_pairs()),
            "not_equivalent": len(self.get_non_equivalent_pairs()),
            "categories": sorted({pair.category for pair in self.pairs}),
        }


def _load_group_pairs(filename: str) -> List[PromptPair]:
    with (DATASETS_DIR / filename).open() as file:
        data = json.load(file)

    pairs: List[PromptPair] = []
    for group in data["prompt_groups"]:
        prompts = group["prompts"]
        label = (
            EquivalenceLabel.EQUIVALENT
            if group["expected_behavior"] == "should_match"
            else EquivalenceLabel.NOT_EQUIVALENT
        )
        for index in range(len(prompts) - 1):
            pairs.append(
                PromptPair(
                    prompt_a=prompts[index],
                    prompt_b=prompts[index + 1],
                    label=label,
                    category=group["topic"],
                    notes=f"Canonical group {group['group_id']}",
                )
            )
    return pairs


def create_default_dataset() -> EvaluationDataset:
    pairs = _load_group_pairs("semantic_duplicates.json")
    pairs.extend(_load_group_pairs("hard_negatives.json"))
    return EvaluationDataset("canonical_v1", pairs)


def create_minimal_dataset() -> EvaluationDataset:
    dataset = create_default_dataset()
    pairs = dataset.get_equivalent_pairs()[:5] + dataset.get_non_equivalent_pairs()[:5]
    return EvaluationDataset("canonical_minimal_v1", pairs)


def get_dataset(name: str = "default") -> EvaluationDataset:
    if name == "minimal":
        return create_minimal_dataset()
    if name != "default":
        raise ValueError(f"Unknown evaluation dataset: {name}")
    return create_default_dataset()
