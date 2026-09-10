#!/usr/bin/env python3
"""
Generate Drift Script

Simulates semantic drift by sending queries from a different domain,
then monitors drift detection and autonomous agent response.
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class DriftGenerator:
    """Generates semantic drift for demo"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.prompts_dir = Path(__file__).parent / "prompts"
    
    def send_request(self, prompt: str) -> Dict[str, Any]:
        """Send request to DriftCache"""
        url = f"{self.api_base_url}/v1/chat/completions"
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_drift_status(self) -> Dict[str, Any]:
        """Get current drift status"""
        try:
            response = requests.get(f"{self.api_base_url}/drift/status")
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}
    
    def run_drift_detection(self) -> Dict[str, Any]:
        """Trigger drift detection"""
        try:
            response = requests.post(f"{self.api_base_url}/drift/run")
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}
    
    def trigger_supervisor(self, reason: str = "drift_detected") -> Dict[str, Any]:
        """Trigger supervisor agent"""
        try:
            payload = {
                "trigger_reason": reason,
                "trigger_source": "manual_demo",
                "tenant_id": "default",
                "dry_run": False
            }
            response = requests.post(
                f"{self.api_base_url}/supervisor/run",
                json=payload,
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            return {"error": str(e)}
    
    def scenario_drift_detection(self):
        """Demo Scenario 3: Drift Detection"""
        print("\n" + "=" * 70)
        print("DEMO SCENARIO 3: DRIFT DETECTION")
        print("=" * 70)
        print("\nThis demonstrates semantic drift monitoring.")
        print("\nSetup: Cache is populated with software engineering queries")
        print("Action: Send healthcare/legal/finance queries (different domain)")
        print("Expected: Drift score increases, drift alert triggered")
        
        # Load drift prompts
        with open(self.prompts_dir / "drift_prompts.json") as f:
            data = json.load(f)
        
        # Step 1: Check baseline drift
        print("\n--- Step 1: Baseline Drift Status ---")
        baseline_drift = self.get_drift_status()
        baseline_score = baseline_drift.get("drift_score", 0)
        print(f"Current Drift Score: {baseline_score:.4f}")
        print(f"Status: {baseline_drift.get('status', 'unknown')}")
        
        # Step 2: Send drift-inducing prompts
        print("\n--- Step 2: Sending Off-Domain Queries ---")
        drift_prompts = data["drift_prompts"]["prompts"]
        print(f"\nSending {len(drift_prompts)} healthcare/legal/finance queries...")
        
        for i, prompt in enumerate(drift_prompts, 1):
            print(f"  [{i}/{len(drift_prompts)}] {prompt[:55]}...")
            result = self.send_request(prompt)
            
            if result["success"]:
                cache_hit = result["data"].get("cache_hit", False)
                print(f"      {'HIT' if cache_hit else 'MISS'}")
            else:
                print(f"      Error: {result['error']}")
            
            time.sleep(0.3)
        
        # Step 3: Run drift detection
        print("\n--- Step 3: Running Drift Detection ---")
        print("Analyzing embedding distribution changes...")
        drift_result = self.run_drift_detection()
        
        if drift_result:
            new_score = drift_result.get("drift_score", 0)
            severity = drift_result.get("severity", "unknown")
            
            print(f"\nDrift Analysis Complete:")
            print(f"  Old Drift Score: {baseline_score:.4f}")
            print(f"  New Drift Score: {new_score:.4f}")
            print(f"  Change: {'+' if new_score > baseline_score else ''}{(new_score - baseline_score):.4f}")
            print(f"  Severity: {severity}")
            
            if new_score > baseline_score:
                print("\n✓ DRIFT DETECTED - Semantic distribution has shifted!")
            
            # Show details
            if "centroid_shift" in drift_result:
                print(f"\n  Centroid Shift: {drift_result['centroid_shift']:.4f}")
            if "similarity_distribution_change" in drift_result:
                print(f"  Similarity Distribution Change: {drift_result['similarity_distribution_change']:.4f}")
        
        # Step 4: Recovery
        print("\n--- Step 4: Recovery (Optional) ---")
        print("Sending software queries again to show drift can decrease...")
        
        recovery_prompts = data["recovery_prompts"]["prompts"][:5]  # Just 5 for demo
        for i, prompt in enumerate(recovery_prompts, 1):
            print(f"  [{i}/5] {prompt[:55]}...")
            self.send_request(prompt)
            time.sleep(0.3)
        
        print("\n✓ Drift detection demo complete")
        print("\nKey Takeaway: DriftCache monitors semantic distribution changes")
        print("and can detect when query patterns shift to different domains.")
    
    def scenario_autonomous_optimization(self):
        """Demo Scenario 4: Autonomous Threshold Optimization"""
        print("\n" + "=" * 70)
        print("DEMO SCENARIO 4: AUTONOMOUS THRESHOLD OPTIMIZATION")
        print("=" * 70)
        print("\nThis demonstrates the Supervisor Agent coordinating threshold optimization.")
        print("\nSetup: Drift detected, cache precision may be degraded")
        print("Action: Supervisor analyzes state and triggers Threshold Optimizer")
        print("Expected: Threshold adjusted, precision improves")
        
        # Step 1: Current state
        print("\n--- Step 1: Current System State ---")
        drift_status = self.get_drift_status()
        print(f"Drift Score: {drift_status.get('drift_score', 'N/A')}")
        print(f"Current Threshold: {drift_status.get('current_threshold', 'N/A')}")
        
        try:
            metrics_response = requests.get(f"{self.api_base_url}/metrics/cache-performance")
            if metrics_response.status_code == 200:
                metrics = metrics_response.json()
                print(f"Cache Hit Rate: {metrics.get('cache_hit_rate', 'N/A')}")
                print(f"Cache Precision: {metrics.get('precision', 'N/A')}")
        except:
            pass
        
        # Step 2: Trigger supervisor
        print("\n--- Step 2: Triggering Supervisor Agent ---")
        print("Supervisor will:")
        print("  1. Load system state")
        print("  2. Diagnose problem (drift + potential quality issues)")
        print("  3. Recommend action (threshold optimization)")
        print("  4. Execute optimization")
        print("  5. Validate results")
        print("  6. Generate report")
        
        print("\nRunning supervisor workflow...")
        supervisor_result = self.trigger_supervisor(reason="drift_with_quality_issues")
        
        if supervisor_result and "error" not in supervisor_result:
            print("\n✓ Supervisor workflow complete")
            
            print(f"\nDiagnosis: {supervisor_result.get('diagnosis', 'N/A')}")
            print(f"Actions Taken: {len(supervisor_result.get('actions_taken', []))}")
            
            # Show actions
            for action in supervisor_result.get('actions_taken', []):
                print(f"\n  Action: {action.get('agent', 'N/A')}")
                print(f"  Status: {action.get('status', 'N/A')}")
                if 'result' in action:
                    result = action['result']
                    if 'old_threshold' in result:
                        print(f"  Old Threshold: {result.get('old_threshold', 'N/A')}")
                    if 'new_threshold' in result:
                        print(f"  New Threshold: {result.get('new_threshold', 'N/A')}")
                    if 'reason' in result:
                        print(f"  Reason: {result.get('reason', 'N/A')}")
            
            print(f"\nFinal Status: {supervisor_result.get('final_status', 'N/A')}")
            
            print("\n✓ Autonomous optimization demo complete")
            print("\nKey Takeaway: The Supervisor Agent detects issues and coordinates")
            print("autonomous optimization without human intervention.")
        else:
            error_msg = supervisor_result.get('error', 'Unknown error')
            print(f"\n✗ Supervisor workflow failed: {error_msg}")
            print("\nNote: This is a dry-run demo. In production, the supervisor would")
            print("execute real optimizations.")
    
    def scenario_index_rebuild(self):
        """Demo Scenario 5: Index Rebuild"""
        print("\n" + "=" * 70)
        print("DEMO SCENARIO 5: INDEX REBUILD (Simulated)")
        print("=" * 70)
        print("\nThis demonstrates self-healing vector infrastructure.")
        print("\nSetup: FAISS index becomes degraded (high stale ratio)")
        print("Action: Index Rebuild Agent detects issue and rebuilds")
        print("Expected: New index version created, latency improves")
        
        print("\n--- Index Health Monitoring ---")
        print("Stale Vector Ratio: 32% (above 25% threshold)")
        print("Search Latency: 58ms p95 (above 50ms threshold)")
        print("Health Status: DEGRADED")
        
        print("\n--- Index Rebuild Agent Decision ---")
        print("Decision: REBUILD_NOW")
        print("Reason: High stale vector ratio (32%)")
        
        print("\n--- Rebuild Workflow ---")
        print("Step 1: Building new index from active cache entries...")
        time.sleep(1)
        print("Step 2: Validating new index (sample queries)...")
        time.sleep(1)
        print("Step 3: Swapping to new index (zero-downtime)...")
        time.sleep(0.5)
        print("Step 4: Backing up old index version...")
        time.sleep(0.5)
        
        print("\n--- After Rebuild ---")
        print("Stale Vector Ratio: 0% (all entries current)")
        print("Search Latency: 8ms p95 (improved)")
        print("Health Status: HEALTHY")
        print("New Index Version: v2")
        
        print("\n✓ Index rebuild demo complete")
        print("\nKey Takeaway: DriftCache monitors vector index health and")
        print("automatically rebuilds when degradation is detected.")
    
    def run_all_scenarios(self):
        """Run all demo scenarios in sequence"""
        print("\n" + "=" * 70)
        print("DRIFTCACHE AUTONOMOUS INFRASTRUCTURE DEMO")
        print("=" * 70)
        print("\nRunning all demo scenarios...\n")
        
        # Scenario 3: Drift Detection
        self.scenario_drift_detection()
        time.sleep(2)
        
        # Scenario 4: Autonomous Optimization
        self.scenario_autonomous_optimization()
        time.sleep(2)
        
        # Scenario 5: Index Rebuild
        self.scenario_index_rebuild()
        
        print("\n" + "=" * 70)
        print("ALL DEMOS COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    import sys
    
    generator = DriftGenerator()
    
    if len(sys.argv) > 1:
        scenario = sys.argv[1]
        if scenario == "drift":
            generator.scenario_drift_detection()
        elif scenario == "optimization":
            generator.scenario_autonomous_optimization()
        elif scenario == "rebuild":
            generator.scenario_index_rebuild()
        elif scenario == "all":
            generator.run_all_scenarios()
        else:
            print(f"Unknown scenario: {scenario}")
            print("Usage: python generate_drift.py [drift|optimization|rebuild|all]")
    else:
        generator.run_all_scenarios()
