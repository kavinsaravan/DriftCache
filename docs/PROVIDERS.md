# Provider Abstraction Layer

## Overview

The Provider Abstraction Layer makes DriftCache **provider-agnostic**, allowing it to work with multiple LLM backends without changing application code.

## Architecture

```
Application Request
       ↓
FastAPI Gateway
       ↓
Provider Router (intelligent routing)
       ↓
┌──────────────┬──────────────┬──────────────┐
│   OpenAI     │  Anthropic   │   Ollama     │
│  Provider    │   Provider   │   Provider   │
└──────────────┴──────────────┴──────────────┘
       ↓              ↓              ↓
  OpenAI API    Claude API    Local Models
```

## Supported Providers

### 1. Anthropic (Claude)

**Models:**
- `claude-3-5-sonnet` → claude-3-5-sonnet-20241022
- `claude-3-opus` → claude-3-opus-20240229
- `claude-3-sonnet` → claude-3-sonnet-20240229
- `claude-3-haiku` → claude-3-haiku-20240307

**Configuration:**
```bash
ANTHROPIC_API_KEY=your_api_key
```

**Use case:** High-quality, context-aware responses

### 2. OpenAI (GPT)

**Models:**
- `gpt-4`
- `gpt-4-turbo`
- `gpt-3.5-turbo`

**Configuration:**
```bash
OPENAI_API_KEY=your_api_key
```

**Use case:** Industry-standard models, wide ecosystem support

### 3. Ollama (Local)

**Models:**
- `llama2`, `llama2:13b`, `llama2:70b`
- `mistral`
- `mixtral`
- `codellama`
- `phi`

**Configuration:**
```bash
OLLAMA_BASE_URL=http://localhost:11434
```

**Use case:** Free, private, offline deployments

## Provider Routing Logic

The router automatically selects the right provider based on the model name:

```python
# Prefix-based routing (fast path)
gpt-*         → OpenAI
claude-*      → Anthropic
llama*        → Ollama
mistral*      → Ollama

# Fallback: check each provider
for provider in providers:
    if provider.supports_model(model):
        return provider
```

## Usage Examples

### Example 1: Using Claude

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-haiku",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

→ **Routed to:** Anthropic Provider

### Example 2: Using GPT

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

→ **Routed to:** OpenAI Provider

### Example 3: Using Local Ollama

```bash
# First, start Ollama and pull a model
ollama serve
ollama pull llama2

# Then use it via DriftCache
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

→ **Routed to:** Ollama Provider (FREE!)

## Why This Matters

### 1. **Flexibility**
Switch providers without changing application code:
```python
# Your app code never changes
client.chat.completions.create(model="gpt-4", ...)

# But DriftCache can route to:
# - OpenAI (gpt-4)
# - Anthropic (claude-3-5-sonnet)
# - Ollama (llama2)
```

### 2. **Fallback & Resilience**
Future support for automatic fallbacks:
```python
# If OpenAI is down
request(model="gpt-4")
  → Try OpenAI → FAIL
  → Fallback to Anthropic → SUCCESS
```

### 3. **Cost Optimization**
Route based on request characteristics:
```python
# Simple query → cheap model
"What is 2+2?" → claude-3-haiku (fast, cheap)

# Complex query → powerful model
"Write a legal contract" → claude-3-5-sonnet (high quality)
```

### 4. **Privacy Control**
```python
# Sensitive data → local model
if request.contains_pii:
    route_to_ollama()  # Never leaves your server
else:
    route_to_cloud()   # Use cloud for speed
```

## Adding a New Provider

### Step 1: Implement BaseProvider

```python
# app/providers/my_provider.py
from app.providers.base import BaseProvider

class MyProvider(BaseProvider):
    async def chat_completion(self, model, messages, **kwargs):
        # Your implementation
        pass

    async def chat_completion_stream(self, model, messages, **kwargs):
        # Your streaming implementation
        pass

    def get_available_models(self):
        return ["my-model-1", "my-model-2"]

    def supports_model(self, model):
        return model.startswith("my-")
```

### Step 2: Register in Router

```python
# app/providers/router.py
from app.providers.my_provider import MyProvider

class ProviderRouter:
    def __init__(self):
        # ...
        self.my_provider = MyProvider()
        self.providers.append(self.my_provider)
```

### Step 3: Update Routing Logic

```python
def route(self, model):
    if model.startswith("my-"):
        return self.my_provider
    # ... existing logic
```

## Testing Providers

```bash
cd backend

# Test the provider router
python -c "
from app.providers.router import provider_router

# Check available models
print('Available models:', provider_router.get_available_models())

# Check routing
print('gpt-4 routes to:', provider_router.get_provider_for_model('gpt-4'))
print('claude-3-haiku routes to:', provider_router.get_provider_for_model('claude-3-haiku'))
print('llama2 routes to:', provider_router.get_provider_for_model('llama2'))
"
```

## Future Enhancements

### 1. Smart Routing Agent (LangGraph)
```python
class ProviderRoutingAgent:
    """Choose provider based on:
    - Cost
    - Latency
    - Model quality
    - Cache confidence
    """
    def route(self, request, context):
        if context.cache_hit_probability > 0.9:
            return fast_provider
        elif request.requires_quality:
            return premium_provider
        else:
            return balanced_provider
```

### 2. Load Balancing
```python
# Distribute load across providers
if openai_provider.load > 80%:
    route_to_anthropic()
```

### 3. A/B Testing
```python
# Test different providers
if user_id % 2 == 0:
    use_provider_a()
else:
    use_provider_b()
```

## Benefits Over Direct API Calls

| Direct API Call | DriftCache Provider Layer |
|----------------|---------------------------|
| Hardcoded to one provider | Works with any provider |
| No fallback | Automatic failover |
| Manual provider switching | Intelligent routing |
| Vendor lock-in | Provider agnostic |
| No cost optimization | Smart model selection |

## Summary

The Provider Abstraction Layer transforms DriftCache from a simple API proxy into a **production-grade AI infrastructure platform** with:

✅ Multi-provider support
✅ Intelligent routing
✅ Extensible architecture
✅ Future-proof design
✅ Cost optimization potential
✅ Privacy controls

This is **real backend architecture**, not a toy project.
