#!/usr/bin/env python3
"""Run maintained DriftCache demos against a configurable API instance."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = PROJECT_ROOT / "datasets"


class DemoError(RuntimeError):
    """Raised when the API cannot complete a demo operation."""


class DriftCacheClient:
    def __init__(self, base_url: str, api_key: str | None, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_body = response.read()
                return json.loads(response_body) if response_body else {}
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise DemoError(
                f"{method} {path} returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise DemoError(f"Could not reach {self.base_url}: {exc.reason}") from exc

    def health(self) -> dict[str, Any]:
        return self.request("GET", "/health")

    def chat(self, prompt: str, model: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/api/v1/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "stream": False,
            },
        )


def load_dataset(filename: str) -> dict[str, Any]:
    with (DATASETS_DIR / filename).open() as file:
        return json.load(file)


def print_chat_result(prompt: str, result: dict[str, Any]) -> None:
    cache_state = "HIT" if result.get("cache_hit") else "MISS"
    similarity = result.get("similarity_score")
    detail = f", similarity={similarity:.3f}" if similarity is not None else ""
    print(f"  {cache_state}{detail}: {prompt}")


def run_health(client: DriftCacheClient, _args: argparse.Namespace) -> None:
    result = client.health()
    print(json.dumps(result, indent=2))
    if result.get("status") not in {"healthy", "degraded"}:
        raise DemoError(f"Unexpected health status: {result.get('status')}")


def run_semantic(client: DriftCacheClient, args: argparse.Namespace) -> None:
    group_count = getattr(args, "groups", 1)
    groups = load_dataset("semantic_duplicates.json")["prompt_groups"][:group_count]
    for group in groups:
        print(f"\n{group['topic']}")
        for prompt in group["prompts"]:
            print_chat_result(prompt, client.chat(prompt, args.model))
            time.sleep(args.delay)


def run_seed(client: DriftCacheClient, args: argparse.Namespace) -> None:
    semantic_groups = load_dataset("semantic_duplicates.json")["prompt_groups"]
    drift_data = load_dataset("drift_prompts.json")
    prompts = drift_data["baseline_prompts"]["prompts"]
    prompts.extend(group["prompts"][0] for group in semantic_groups)
    for index, prompt in enumerate(prompts, start=1):
        print(f"[{index}/{len(prompts)}]", end="")
        print_chat_result(prompt, client.chat(prompt, args.model))
        time.sleep(args.delay)


def run_drift(client: DriftCacheClient, args: argparse.Namespace) -> None:
    data = load_dataset("drift_prompts.json")
    baseline = data["baseline_prompts"]["prompts"]
    shifted = data["drift_prompts"]["prompts"]

    print("Seeding the reference domain...")
    for prompt in baseline:
        print_chat_result(prompt, client.chat(prompt, args.model))
        time.sleep(args.delay)

    print("\nSending shifted-domain prompts...")
    for prompt in shifted:
        print_chat_result(prompt, client.chat(prompt, args.model))
        time.sleep(args.delay)

    result = client.request("POST", "/api/v1/drift/run-check")
    print("\nDrift result:")
    print(json.dumps(result, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("DRIFTCACHE_API_URL", "http://localhost:8000"),
        help="API origin, without /api/v1",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("DRIFTCACHE_API_KEY") or os.getenv("API_KEY"),
        help="API key; defaults to DRIFTCACHE_API_KEY or API_KEY",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--delay", type=float, default=0.2)

    subparsers = parser.add_subparsers(dest="scenario", required=True)
    subparsers.add_parser("health", help="Check API, database, and Redis health")
    semantic = subparsers.add_parser("semantic", help="Show semantic cache reuse")
    semantic.add_argument("--groups", type=int, default=1)
    subparsers.add_parser("seed", help="Populate representative cache entries")
    subparsers.add_parser("drift", help="Send a domain shift and run drift detection")
    subparsers.add_parser("all", help="Run health, semantic, and drift demos")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = DriftCacheClient(args.base_url, args.api_key, args.timeout)
    runners = {
        "health": run_health,
        "semantic": run_semantic,
        "seed": run_seed,
        "drift": run_drift,
    }
    try:
        if args.scenario == "all":
            run_health(client, args)
            run_semantic(client, args)
            run_drift(client, args)
        else:
            runners[args.scenario](client, args)
    except (DemoError, OSError, ValueError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
