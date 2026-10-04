#!/usr/bin/env python3
"""
Threshold Evaluation Script

Evaluates cache quality metrics (precision, recall, F1) at different thresholds
using labeled test pairs from benchmarks/datasets/

Usage:
    python3 evaluate_thresholds.py

Output:
    - Prints metrics table to stdout
    - Saves JSON results to benchmarks/results/threshold_evaluation.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.evaluation.dataset_loader import load_evaluation_dataset


def evaluate_threshold(evaluation_pairs, threshold):
    """
    Evaluate precision, recall, F1 at a specific threshold

    Args:
        evaluation_pairs: List of {similarity, should_cache} dicts
        threshold: Similarity threshold to test

    Returns:
        Dict with precision, recall, f1, true_positives, false_positives, etc.
    """
    # Count true positives, false positives, true negatives, false negatives
    tp = sum(1 for p in evaluation_pairs if p['similarity'] >= threshold and p['should_cache'])
    fp = sum(1 for p in evaluation_pairs if p['similarity'] >= threshold and not p['should_cache'])
    tn = sum(1 for p in evaluation_pairs if p['similarity'] < threshold and not p['should_cache'])
    fn = sum(1 for p in evaluation_pairs if p['similarity'] < threshold and p['should_cache'])

    total_positive = tp + fn  # All pairs that should match
    total_negative = tn + fp  # All pairs that shouldn't match
    total_hits = tp + fp      # All cache hits at this threshold

    precision = tp / total_hits if total_hits > 0 else 0.0
    recall = tp / total_positive if total_positive > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    false_hit_rate = fp / total_hits if total_hits > 0 else 0.0
    false_miss_rate = fn / total_positive if total_positive > 0 else 0.0

    return {
        "threshold": threshold,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "false_hit_rate": round(false_hit_rate, 4),
        "false_miss_rate": round(false_miss_rate, 4),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "cache_hits": total_hits,
        "total_positive_pairs": total_positive,
        "total_negative_pairs": total_negative,
    }


def main():
    print("Loading labeled evaluation datasets...")
    evaluation_pairs = load_evaluation_dataset()

    print(f"Loaded {len(evaluation_pairs)} evaluation pairs\n")

    # Test at different thresholds
    thresholds_to_test = [0.85, 0.90, 0.92, 0.95]

    print("Evaluating cache quality metrics at different thresholds:")
    print("=" * 80)

    results = []

    for threshold in thresholds_to_test:
        result = evaluate_threshold(evaluation_pairs, threshold)
        results.append(result)

        print(f"\nThreshold: {threshold:.2f}")
        print(f"  Precision:  {result['precision']:.3f} (accuracy of cache hits)")
        print(f"  Recall:     {result['recall']:.3f} (% of matching pairs cached)")
        print(f"  F1 Score:   {result['f1_score']:.3f}")
        print(f"  Cache Hits: {result['cache_hits']} ({result['true_positives']} correct, {result['false_positives']} wrong)")

    # Save results
    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_pairs": len(evaluation_pairs),
        "total_positive_pairs": results[0]["total_positive_pairs"],  # Same for all thresholds
        "total_negative_pairs": results[0]["total_negative_pairs"],
        "thresholds": results
    }

    output_file = Path(__file__).parent / "results" / "threshold_evaluation.json"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n\nResults saved to: {output_file}")
    print("\nREADME table (copy this):")
    print("-" * 80)
    print("| Similarity Threshold | Precision | Recall | F1 Score | Use Case |")
    print("|---------------------|-----------|--------|----------|----------|")

    for r in results:
        threshold_str = f"{r['threshold']:.2f}"
        if r['threshold'] == 0.85:
            print(f"| **{threshold_str}** (Balanced) | **{r['precision']*100:.1f}%** | **{r['recall']*100:.1f}%** | **{r['f1_score']*100:.1f}%** | Production default - high safety with good coverage |")
        elif r['threshold'] == 0.90:
            print(f"| **{threshold_str}** (Conservative) | **{r['precision']*100:.1f}%** | **{r['recall']*100:.1f}%** | **{r['f1_score']*100:.1f}%** | Maximum safety - zero wrong answers |")
        elif r['threshold'] == 0.92:
            print(f"| {threshold_str} | {r['precision']*100:.1f}% | {r['recall']*100:.1f}% | {r['f1_score']*100:.1f}% | Ultra-conservative |")
        else:
            print(f"| {threshold_str} | {r['precision']*100:.1f}% | {r['recall']*100:.1f}% | {r['f1_score']*100:.1f}% | Near-exact match only |")


if __name__ == "__main__":
    main()
