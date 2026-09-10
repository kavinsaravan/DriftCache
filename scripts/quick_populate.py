#!/usr/bin/env python3
"""Quick demo data population - creates cache hits fast"""
import requests
import time

API_URL = "https://driftcache-api-production.up.railway.app/api/v1/chat/completions"

# Simple prompts that will generate cache hits
PROMPTS = [
    "Hello!",
    "What is 2+2?",
    "Say hi",
]

print("Quick Demo Data Population")
print("=" * 50)

# Send each prompt 3 times to create cache hits
for i, prompt in enumerate(PROMPTS):
    print(f"\n[{i+1}/{len(PROMPTS)}] Testing prompt: '{prompt}'")

    for attempt in range(3):
        try:
            response = requests.post(
                API_URL,
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "model": "gpt-4o-mini",
                    "max_tokens": 20,
                    "temperature": 0.7,
                    "stream": False
                },
                timeout=30
            )

            if response.status_code == 200:
                print(f"  ✓ Attempt {attempt+1}: Success")
            else:
                print(f"  ✗ Attempt {attempt+1}: {response.status_code}")

        except Exception as e:
            print(f"  ✗ Attempt {attempt+1}: {str(e)[:50]}")

        time.sleep(1)  # Small delay between requests

print("\n" + "=" * 50)
print("Done! Check your dashboard for cache hit data.")
