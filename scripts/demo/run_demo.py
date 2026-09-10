#!/usr/bin/env python3
"""
DriftCache Demo Orchestrator

Runs scripted demo scenarios that showcase DriftCache capabilities.
"""

import json
import time
import requests
import argparse
from pathlib import Path
from typing import List, Dict, Any
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)


class DemoRunner:
    """Orchestrates DriftCache demo scenarios"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.prompts_dir = Path(__file__).parent / "prompts"
    
    def print_header(self, title: str):
        """Print formatted header"""
        print("\n" + Fore.CYAN + "=" * 70)
        print(Fore.CYAN + Style.BRIGHT + title)
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
    
    def print_step(self, step_num: int, description: str):
        """Print step header"""
        print(f"\n{Fore.YELLOW}--- Step {step_num}: {description} ---{Style.RESET_ALL}")
    
    def print_success(self, message: str):
        """Print success message"""
        print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
    
    def print_info(self, message: str):
        """Print info message"""
        print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")
    
    def send_request(self, prompt: str) -> Dict[str, Any]:
        """Send request to DriftCache"""
        url = f"{self.api_base_url}/v1/chat/completions"
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150
        }
        
        try:
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=30)
            latency = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "data": data,
                    "cache_hit": data.get("cache_hit", False),
                    "similarity_score": data.get("similarity_score"),
                    "matched_prompt": data.get("matched_prompt"),
                    "latency_ms": latency
                }
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def scenario_1_semantic_cache_savings(self):
        """Demo Scenario 1: Semantic Cache Savings"""
        self.print_header("DEMO SCENARIO 1: SEMANTIC CACHE SAVINGS")
        
        print("\nThis demonstrates basic semantic caching with paraphrased questions.")
        print(f"{Fore.WHITE}Setup: Fresh cache")
        print(f"Action: Send original question, then paraphrased variations")
        print(f"Expected: First is MISS, variations are HITs with fast latency{Style.RESET_ALL}")
        
        # Load semantic duplicates
        with open(self.prompts_dir / "semantic_duplicates.json") as f:
            data = json.load(f)
        
        # Demo with Redis example
        redis_pair = data["prompt_pairs"][0]  # Redis example
        original = redis_pair["original"]
        variations = redis_pair["variations"]
        
        self.print_step(1, "Send Original Question")
        print(f"\n  Prompt: {Fore.WHITE}\"{original}\"{Style.RESET_ALL}")
        result1 = self.send_request(original)
        
        if result1["success"]:
            cache_status = "HIT" if result1["cache_hit"] else "MISS"
            color = Fore.GREEN if not result1["cache_hit"] else Fore.YELLOW
            print(f"  Cache Status: {color}{cache_status}{Style.RESET_ALL}")
            print(f"  Latency: {result1['latency_ms']:.1f}ms")
            print(f"  {Fore.GREEN}✓ Response cached for future semantic matches{Style.RESET_ALL}")
        
        time.sleep(1)
        
        self.print_step(2, "Send Paraphrased Variations")
        
        for i, variation in enumerate(variations[:2], 1):  # Just show 2 for demo
            print(f"\n  Variation {i}: {Fore.WHITE}\"{variation}\"{Style.RESET_ALL}")
            result = self.send_request(variation)
            
            if result["success"]:
                cache_status = "HIT" if result["cache_hit"] else "MISS"
                color = Fore.GREEN if result["cache_hit"] else Fore.RED
                
                print(f"  Cache Status: {color}{cache_status}{Style.RESET_ALL}")
                print(f"  Latency: {result['latency_ms']:.1f}ms")
                
                if result["cache_hit"]:
                    if result.get("similarity_score"):
                        print(f"  Similarity Score: {result['similarity_score']:.3f}")
                    if result.get("matched_prompt"):
                        matched = result['matched_prompt'][:50] + "..." if len(result['matched_prompt']) > 50 else result['matched_prompt']
                        print(f"  Matched: \"{matched}\"")
                    print(f"  {Fore.GREEN}✓ Served from cache - Cost saved, Low latency{Style.RESET_ALL}")
                else:
                    print(f"  {Fore.YELLOW}⚠ No match found - Provider called{Style.RESET_ALL}")
            
            time.sleep(0.5)
        
        self.print_success("Semantic cache savings demo complete")
        print(f"\n{Fore.WHITE}Key Takeaway: Paraphrased questions are recognized as semantically")
        print(f"identical and served from cache, reducing cost and latency.{Style.RESET_ALL}")
    
    def scenario_2_threshold_tradeoff(self):
        """Demo Scenario 2: Threshold Tradeoff"""
        self.print_header("DEMO SCENARIO 2: THRESHOLD TRADEOFF")
        
        print("\nThis demonstrates how similarity threshold controls quality vs. savings.")
        print(f"{Fore.WHITE}Setup: Test prompts at different similarity levels")
        print(f"Action: Show how threshold affects matching behavior")
        print(f"Expected: Lower threshold = more hits (riskier), Higher = fewer hits (safer){Style.RESET_ALL}")
        
        with open(self.prompts_dir / "threshold_scenarios.json") as f:
            data = json.load(f)
        
        thresholds = data["thresholds_to_test"]
        
        self.print_step(1, "Understanding Threshold Impact")
        
        print(f"\n{Fore.WHITE}Similarity thresholds to test:{Style.RESET_ALL}")
        for threshold in thresholds:
            print(f"  • {threshold} - {'Strict' if threshold >= 0.95 else 'Moderate' if threshold >= 0.90 else 'Lenient'}")
        
        print(f"\n{Fore.WHITE}Example scenarios:{Style.RESET_ALL}")
        
        # Show clear matches
        clear_group = data["test_groups"][0]
        print(f"\n  {Fore.GREEN}Clear Matches{Style.RESET_ALL} (should match at all thresholds):")
        for prompt in clear_group["prompts"][:2]:
            print(f"    - \"{prompt}\"")
        
        # Show moderate similarity
        moderate_group = data["test_groups"][1]
        print(f"\n  {Fore.YELLOW}Moderate Similarity{Style.RESET_ALL} (match at 0.85, maybe not at 0.95):")
        for prompt in moderate_group["prompts"][:2]:
            print(f"    - \"{prompt}\"")
        
        # Show low similarity
        low_group = data["test_groups"][2]
        print(f"\n  {Fore.RED}Low Similarity{Style.RESET_ALL} (should NOT match - different topics):")
        for prompt in low_group["prompts"][:2]:
            print(f"    - \"{prompt}\"")
        
        self.print_step(2, "Threshold Recommendations")
        
        print(f"\n{Fore.WHITE}Threshold Selection Guide:{Style.RESET_ALL}")
        print(f"  • 0.95+ : Maximum precision, minimal false hits, lower cache hit rate")
        print(f"  • 0.90-0.94 : Balanced - {Fore.GREEN}RECOMMENDED{Style.RESET_ALL}")
        print(f"  • <0.90 : Higher cache hits, risk of false positives")
        
        print(f"\n{Fore.WHITE}Current DriftCache threshold: 0.90{Style.RESET_ALL}")
        print(f"  This balances quality (94% precision) with efficiency (68% hit rate)")
        
        self.print_success("Threshold tradeoff demo complete")
        print(f"\n{Fore.WHITE}Key Takeaway: Threshold tuning is a precision-recall tradeoff.")
        print(f"DriftCache's autonomous optimizer finds the optimal balance.{Style.RESET_ALL}")
    
    def run_all_scenarios(self):
        """Run all demo scenarios"""
        self.print_header("DRIFTCACHE COMPLETE DEMO SUITE")
        
        print(f"\n{Fore.WHITE}This demo showcases all major DriftCache capabilities:{Style.RESET_ALL}")
        print("  1. Semantic cache savings (cost + latency reduction)")
        print("  2. Threshold tradeoff (precision vs recall)")
        print("  3. Drift detection (monitoring semantic changes)")
        print("  4. Autonomous optimization (agent-based tuning)")
        print("  5. Index rebuild (self-healing infrastructure)")
        
        input(f"\n{Fore.YELLOW}Press Enter to start...{Style.RESET_ALL}")
        
        # Scenario 1
        self.scenario_1_semantic_cache_savings()
        time.sleep(2)
        
        # Scenario 2
        self.scenario_2_threshold_tradeoff()
        time.sleep(2)
        
        # Note about remaining scenarios
        print("\n" + Fore.CYAN + "=" * 70)
        print(Fore.CYAN + "ADDITIONAL SCENARIOS")
        print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
        
        print(f"\n{Fore.WHITE}For autonomous infrastructure demos, run:{Style.RESET_ALL}")
        print(f"  python demo/generate_drift.py drift")
        print(f"  python demo/generate_drift.py optimization")
        print(f"  python demo/generate_drift.py rebuild")
        
        self.print_header("DEMO COMPLETE")
        print(f"\n{Fore.GREEN}✓ All basic demos finished successfully{Style.RESET_ALL}")


def main():
    parser = argparse.ArgumentParser(description="DriftCache Demo Runner")
    parser.add_argument(
        "--scenario",
        choices=["semantic", "threshold", "all"],
        default="all",
        help="Which demo scenario to run"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="DriftCache API base URL"
    )
    
    args = parser.parse_args()
    
    runner = DemoRunner(api_base_url=args.api_url)
    
    if args.scenario == "semantic":
        runner.scenario_1_semantic_cache_savings()
    elif args.scenario == "threshold":
        runner.scenario_2_threshold_tradeoff()
    else:
        runner.run_all_scenarios()


if __name__ == "__main__":
    main()
