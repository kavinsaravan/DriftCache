# DriftCache API Examples

## OpenAI-Compatible Gateway Endpoints

### 1. List Available Models

```bash
curl http://localhost:8000/api/v1/models
```

Expected response:
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4",
      "object": "model",
      "created": 1234567890,
      "owned_by": "driftcache"
    },
    ...
  ]
}
```

### 2. Chat Completion (Non-Streaming)

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello! What is DriftCache?"}
    ],
    "temperature": 0.7,
    "max_tokens": 150
  }'
```

Expected response:
```json
{
  "id": "chatcmpl-1234567890",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "claude-3-5-sonnet-20241022",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "DriftCache is..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 25,
    "total_tokens": 35
  }
}
```

### 3. Chat Completion (Streaming)

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Count from 1 to 5"}
    ],
    "temperature": 0.7,
    "max_tokens": 100,
    "stream": true
  }'
```

Expected response (SSE format):
```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{"content":"1"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":...,"model":"...","choices":[{"index":0,"delta":{"content":", "},"finish_reason":null}]}

...

data: [DONE]
```

### 4. Using with OpenAI Python SDK

You can use DriftCache as a drop-in replacement for OpenAI:

```python
from openai import OpenAI

# Point to DriftCache instead of OpenAI
client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="dummy"  # Not used yet, but required by SDK
)

# Use exactly like OpenAI
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Hello from DriftCache!"}
    ]
)

print(response.choices[0].message.content)
```

### 5. Streaming with OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="dummy"
)

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Count to 10"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end='', flush=True)
```

## Model Mapping

DriftCache automatically maps OpenAI model names to Claude models:

| OpenAI Model | Claude Model |
|--------------|--------------|
| `gpt-4` | `claude-3-5-sonnet-20241022` |
| `gpt-4-turbo` | `claude-3-5-sonnet-20241022` |
| `gpt-3.5-turbo` | `claude-3-haiku-20240307` |
| `claude-3-5-sonnet` | `claude-3-5-sonnet-20241022` |
| `claude-3-opus` | `claude-3-opus-20240229` |
| `claude-3-sonnet` | `claude-3-sonnet-20240229` |
| `claude-3-haiku` | `claude-3-haiku-20240307` |

## Error Handling

If a request fails, you'll receive an error response:

```json
{
  "error": {
    "message": "Invalid request",
    "type": "invalid_request_error",
    "code": "invalid_messages"
  }
}
```

## Testing the API

### Method 1: Using the test script

```bash
cd backend
python tests/test_gateway.py
```

### Method 2: Using curl (see examples above)

### Method 3: Using the OpenAPI docs

Visit http://localhost:8000/docs for interactive API documentation.
