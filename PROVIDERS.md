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
