import json
from types import SimpleNamespace

from app.evaluation.dataset_loader import load_threshold_evaluation_pairs


class FakeEmbeddingService:
    def embed_text(self, text):
        vector = [1.0, 0.0] if text.startswith("same") else [0.0, 1.0]
        return SimpleNamespace(vector=vector)


def test_load_threshold_evaluation_pairs_uses_labeled_groups(tmp_path):
    path = tmp_path / "pairs.json"
    path.write_text(
        json.dumps(
            {
                "prompt_groups": [
                    {
                        "expected_behavior": "should_match",
                        "prompts": ["same a", "same b"],
                    }
                ]
            }
        )
    )

    pairs = load_threshold_evaluation_pairs(
        [str(path)], embedding_service=FakeEmbeddingService()
    )
    assert pairs == [
        {
            "similarity": 1.0,
            "should_cache": True,
            "prompt1": "same a",
            "prompt2": "same b",
        }
    ]
