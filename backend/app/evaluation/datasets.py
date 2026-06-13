"""
Evaluation Datasets Module

Creates and manages test datasets for cache quality evaluation
"""
from typing import List, Dict, Literal
from dataclasses import dataclass
from enum import Enum


class EquivalenceLabel(str, Enum):
    """Labels for prompt pair equivalence"""
    EQUIVALENT = "equivalent"               # Should reuse cache
    NOT_EQUIVALENT = "not_equivalent"       # Should NOT reuse cache
    PARTIALLY_EQUIVALENT = "partially_equivalent"  # Edge case


@dataclass
class PromptPair:
    """
    Test case: pair of prompts with equivalence label

    Used to evaluate whether cache makes correct hit/miss decisions
    """
    prompt_a: str
    prompt_b: str
    label: EquivalenceLabel
    category: str  # e.g., "docker", "python", "system_design"
    notes: str = ""

    def should_cache_hit(self) -> bool:
        """Whether these prompts should share cached response"""
        return self.label == EquivalenceLabel.EQUIVALENT


class EvaluationDataset:
    """Collection of test prompt pairs"""

    def __init__(self, name: str, pairs: List[PromptPair]):
        self.name = name
        self.pairs = pairs

    def __len__(self):
        return len(self.pairs)

    def get_equivalent_pairs(self) -> List[PromptPair]:
        """Get pairs that should share cache"""
        return [p for p in self.pairs if p.label == EquivalenceLabel.EQUIVALENT]

    def get_non_equivalent_pairs(self) -> List[PromptPair]:
        """Get pairs that should NOT share cache"""
        return [p for p in self.pairs if p.label == EquivalenceLabel.NOT_EQUIVALENT]

    def summary(self) -> Dict:
        """Dataset statistics"""
        return {
            "name": self.name,
            "total_pairs": len(self.pairs),
            "equivalent": len(self.get_equivalent_pairs()),
            "not_equivalent": len(self.get_non_equivalent_pairs()),
            "categories": list(set(p.category for p in self.pairs))
        }


def create_default_dataset() -> EvaluationDataset:
    """
    Create default evaluation dataset

    Covers common semantic caching edge cases
    """
    pairs = [
        # Clear equivalents - different wording, same meaning
        PromptPair(
            "What is Docker?",
            "Explain Docker to me",
            EquivalenceLabel.EQUIVALENT,
            "docker",
            "Basic synonym variation"
        ),
        PromptPair(
            "How does Redis work?",
            "Explain how Redis works",
            EquivalenceLabel.EQUIVALENT,
            "redis",
            "Question vs statement form"
        ),
        PromptPair(
            "Write a Python function to reverse a string",
            "Create a Python function that reverses a string",
            EquivalenceLabel.EQUIVALENT,
            "python",
            "Write vs create synonym"
        ),
        PromptPair(
            "Explain binary search simply",
            "What is binary search in simple terms?",
            EquivalenceLabel.EQUIVALENT,
            "algorithms",
            "Different question structure, same intent"
        ),
        PromptPair(
            "List the benefits of microservices",
            "What are the advantages of microservices?",
            EquivalenceLabel.EQUIVALENT,
            "architecture",
            "Benefits vs advantages synonym"
        ),

        # Clear non-equivalents - different topics
        PromptPair(
            "Explain Docker containers",
            "Explain Docker networking",
            EquivalenceLabel.NOT_EQUIVALENT,
            "docker",
            "Different Docker subtopics"
        ),
        PromptPair(
            "How to use Python lists?",
            "How to use Python dictionaries?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "python",
            "Different data structures"
        ),
        PromptPair(
            "What is a REST API?",
            "What is a GraphQL API?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "api",
            "Different API types"
        ),
        PromptPair(
            "Explain supervised learning",
            "Explain unsupervised learning",
            EquivalenceLabel.NOT_EQUIVALENT,
            "ml",
            "Different ML paradigms"
        ),
        PromptPair(
            "How to optimize SQL queries?",
            "How to optimize React rendering?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "optimization",
            "Different optimization domains"
        ),

        # Tricky cases - similar but different specificity
        PromptPair(
            "Explain Docker",
            "Explain Docker Compose",
            EquivalenceLabel.NOT_EQUIVALENT,
            "docker",
            "General vs specific tool"
        ),
        PromptPair(
            "What is sorting?",
            "What is quicksort?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "algorithms",
            "General concept vs specific algorithm"
        ),
        PromptPair(
            "How to deploy to production?",
            "How to deploy to AWS?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "deployment",
            "General vs platform-specific"
        ),

        # Edge cases - same words, different context
        PromptPair(
            "What is Python?",
            "What is a python?",  # the snake
            EquivalenceLabel.NOT_EQUIVALENT,
            "ambiguous",
            "Programming language vs animal"
        ),
        PromptPair(
            "Explain React hooks",
            "Explain fishing hooks",
            EquivalenceLabel.NOT_EQUIVALENT,
            "ambiguous",
            "Technical term vs physical object"
        ),

        # Specificity variations - equivalent
        PromptPair(
            "Explain binary search",
            "Explain the binary search algorithm",
            EquivalenceLabel.EQUIVALENT,
            "algorithms",
            "With/without 'algorithm' qualifier"
        ),
        PromptPair(
            "How does caching work?",
            "How does cache work?",
            EquivalenceLabel.EQUIVALENT,
            "caching",
            "Caching vs cache"
        ),
        PromptPair(
            "What are the SOLID principles?",
            "Explain SOLID principles in software engineering",
            EquivalenceLabel.EQUIVALENT,
            "software_engineering",
            "Brief vs detailed question"
        ),

        # Format variations - equivalent
        PromptPair(
            "List 5 benefits of Docker",
            "What are the benefits of Docker?",
            EquivalenceLabel.EQUIVALENT,
            "docker",
            "Specific count vs open-ended"
        ),
        PromptPair(
            "Compare REST and GraphQL",
            "What are the differences between REST and GraphQL?",
            EquivalenceLabel.EQUIVALENT,
            "api",
            "Compare vs differences"
        ),

        # Non-equivalent - different depth
        PromptPair(
            "What is Kubernetes?",
            "How does Kubernetes scheduling work internally?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "kubernetes",
            "Introduction vs deep technical detail"
        ),
        PromptPair(
            "Explain neural networks simply",
            "Explain backpropagation in neural networks mathematically",
            EquivalenceLabel.NOT_EQUIVALENT,
            "ml",
            "Simple overview vs mathematical detail"
        ),
    ]

    return EvaluationDataset("default_v1", pairs)


def create_minimal_dataset() -> EvaluationDataset:
    """
    Create minimal dataset for quick testing

    Just 10 pairs covering basic cases
    """
    pairs = [
        # 5 equivalents
        PromptPair(
            "What is Docker?",
            "Explain Docker",
            EquivalenceLabel.EQUIVALENT,
            "docker"
        ),
        PromptPair(
            "How does Redis work?",
            "Explain Redis",
            EquivalenceLabel.EQUIVALENT,
            "redis"
        ),
        PromptPair(
            "Write a Python function to sort a list",
            "Create a Python function for sorting lists",
            EquivalenceLabel.EQUIVALENT,
            "python"
        ),
        PromptPair(
            "List benefits of microservices",
            "What are microservices advantages?",
            EquivalenceLabel.EQUIVALENT,
            "architecture"
        ),
        PromptPair(
            "Explain REST APIs",
            "What is a REST API?",
            EquivalenceLabel.EQUIVALENT,
            "api"
        ),

        # 5 non-equivalents
        PromptPair(
            "Explain Docker containers",
            "Explain Docker networking",
            EquivalenceLabel.NOT_EQUIVALENT,
            "docker"
        ),
        PromptPair(
            "How to use Python lists?",
            "How to use Python dictionaries?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "python"
        ),
        PromptPair(
            "What is supervised learning?",
            "What is unsupervised learning?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "ml"
        ),
        PromptPair(
            "Explain binary search",
            "Explain quicksort",
            EquivalenceLabel.NOT_EQUIVALENT,
            "algorithms"
        ),
        PromptPair(
            "What is React?",
            "What is Vue.js?",
            EquivalenceLabel.NOT_EQUIVALENT,
            "frontend"
        ),
    ]

    return EvaluationDataset("minimal_v1", pairs)


def get_dataset(name: str = "default") -> EvaluationDataset:
    """
    Get evaluation dataset by name

    Args:
        name: Dataset name ('default' or 'minimal')

    Returns:
        EvaluationDataset
    """
    if name == "minimal":
        return create_minimal_dataset()
    else:
        return create_default_dataset()
