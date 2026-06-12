# Streaming Response System

## Overview

The Streaming Response System enables DriftCache to stream tokens back to clients in real-time, creating a ChatGPT-like experience where users see responses as they're generated.

## Why Streaming Matters

### Without Streaming
```
Request sent → Wait 10 seconds → Full response arrives
```
User experience: **Waiting...**

### With Streaming
```
Request sent → Token 1 (50ms) → Token 2 (100ms) → Token 3 (150ms) → ...
```
User experience: **Immediate feedback**

## Architecture

```
Client Request (stream=true)
       ↓
FastAPI Gateway
       ↓
StreamCollector (intercepts)
       ↓
┌──────────────┬──────────────┐
│  Forward     │   Collect    │
│  to Client   │  for Cache   │
└──────────────┴──────────────┘
       ↓              ↓
   Real-time      Background
   Streaming      Collection
```

## Two Critical Paths

### Path 1: Cache Miss (Stream from Provider)

```python
# User makes request
POST /v1/chat/completions
{
  "model": "gpt-4",
  "messages": [...],
  "stream": true
}

# DriftCache:
1. Check cache → MISS
2. Create StreamCollector
3. Start provider stream
4. For each chunk:
   a. Send to client immediately
   b. Collect for caching
5. When stream completes:
   a. Cache full response
   b. Log metrics
```

### Path 2: Cache Hit (Stream from Cache)

```python
# User makes request
POST /v1/chat/completions
{
  "model": "gpt-4",
  "messages": [...],
  "stream": true
}

# DriftCache:
1. Check cache → HIT
2. Create simulated stream from cached content
3. Stream cached content in chunks
4. Log cache hit
```

## Server-Sent Events (SSE) Format

All streaming responses use SSE format:

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-4","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-4","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1234567890,"model":"gpt-4","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

## Key Components

### 1. SSEFormatter

Converts data into SSE format:

```python
from app.services.streaming import SSEFormatter

# Format a chunk
chunk = ChatCompletionStreamResponse(...)
sse_chunk = SSEFormatter.format_chunk(chunk)
# → "data: {...}\n\n"

# Format completion
done = SSEFormatter.format_done()
# → "data: [DONE]\n\n"

# Format errors
error = SSEFormatter.format_error("Something went wrong")
# → "data: {"error": {...}}\n\n"
```

### 2. StreamCollector

Simultaneously forwards chunks AND collects them for caching:

```python
from app.services.streaming import StreamCollector

# Create collector
collector = StreamCollector(
    completion_id="chatcmpl-123",
    model="gpt-4"
)

# Define what to do when stream completes
async def on_complete(response):
    # Cache the response
    await cache.store(response)

# Wrap provider stream
collected_stream = collector.collect_and_forward(
    stream=provider_stream,
    on_complete=on_complete
)

# Return to client
return StreamingResponse(collected_stream, media_type="text/event-stream")
```

### 3. Cached Stream Generator

Creates a stream from cached content:

```python
from app.services.streaming import create_cached_stream

# When cache hit
cached_content = "This is a cached response"

# Generate simulated stream
stream = create_cached_stream(
    content=cached_content,
    model="gpt-4",
    chunk_size=5  # words per chunk
)

# Return to client
return StreamingResponse(stream, media_type="text/event-stream")
```

## Usage Examples

### Example 1: Streaming Request (curl)

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Count from 1 to 5"}
    ],
    "stream": true
  }'
```

Output:
```
data: {"id":"chatcmpl-...","choices":[{"delta":{"role":"assistant"},...}]}

data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"1"},...}]}

data: {"id":"chatcmpl-...","choices":[{"delta":{"content":", "},...}]}

data: {"id":"chatcmpl-...","choices":[{"delta":{"content":"2"},...}]}

...

data: [DONE]
```

### Example 2: Streaming with OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/api/v1",
    api_key="dummy"
)

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a haiku about caching"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end='', flush=True)
```

Output:
```
Data flows so fast
Cached responses save the day
Latency now past
```

### Example 3: Streaming with JavaScript

```javascript
const response = await fetch('http://localhost:8000/api/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'gpt-4',
    messages: [
      { role: 'user', content: 'Hello!' }
    ],
    stream: true
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = line.slice(6);
      if (data === '[DONE]') {
        console.log('Stream completed!');
      } else {
        const parsed = JSON.parse(data);
        const content = parsed.choices[0]?.delta?.content;
        if (content) {
          process.stdout.write(content);
        }
      }
    }
  }
}
```

## The Caching Challenge

Streaming introduces a critical challenge: **How do you cache a response while you're streaming it?**

### The Problem

```
Provider sends: Token 1 → Token 2 → Token 3 → ...
Client receives: Token 1 → Token 2 → Token 3 → ...

Question: When do we cache?
Answer: AFTER the stream completes, but we collect DURING streaming
```

### The Solution

DriftCache uses **StreamCollector**:

```python
# Simultaneously:
# 1. Forward chunks to client
# 2. Collect chunks in background

async for chunk in provider_stream:
    # Forward immediately
    yield chunk

    # Collect in background
    collector.add_chunk(chunk)

# When done
collected_response = collector.get_response()
await cache.store(collected_response)
```

## Error Handling

### Stream Errors

If an error occurs during streaming:

```python
try:
    async for chunk in provider_stream:
        yield chunk
except Exception as e:
    # Send error to client
    error_chunk = SSEFormatter.format_error(str(e))
    yield error_chunk
```

### Connection Drops

If client disconnects:

```python
async for chunk in provider_stream:
    try:
        yield chunk
    except asyncio.CancelledError:
        # Client disconnected
        logger.info("Client disconnected during stream")
        break
```

## Performance Considerations

### 1. Buffering

Disable nginx buffering to prevent delayed streaming:

```nginx
location /api {
    proxy_pass http://backend;
    proxy_buffering off;  # Critical for streaming
}
```

Or set headers:

```python
return StreamingResponse(
    stream,
    headers={"X-Accel-Buffering": "no"}
)
```

### 2. Chunk Size

Balance between:
- **Small chunks**: More real-time, more overhead
- **Large chunks**: Less overhead, less real-time

```python
# Fast streaming (1-3 words)
create_cached_stream(content, chunk_size=2)

# Balanced (5 words)
create_cached_stream(content, chunk_size=5)

# Slower but efficient (10 words)
create_cached_stream(content, chunk_size=10)
```

### 3. Heartbeats

Keep connections alive with heartbeat comments:

```python
from app.services.streaming import stream_with_heartbeat

stream = stream_with_heartbeat(
    provider_stream,
    heartbeat_interval=15  # seconds
)
```

## Testing

Run streaming tests:

```bash
cd backend
pytest tests/test_streaming.py -v
```

Test manually:

```bash
# Start server
uvicorn app.main:app --reload

# Test streaming
python tests/test_gateway.py
```

## Future Enhancements

### 1. Streaming Metrics

```python
class StreamMetrics:
    first_token_latency: float
    tokens_per_second: float
    total_tokens: int
    stream_duration: float
```

### 2. Adaptive Chunking

```python
# Adjust chunk size based on content
if response.is_code:
    chunk_size = 10  # Larger chunks for code
elif response.is_conversation:
    chunk_size = 3   # Smaller chunks for chat
```

### 3. Stream Compression

```python
# Compress streams for bandwidth savings
return StreamingResponse(
    compressed_stream,
    headers={"Content-Encoding": "gzip"}
)
```

## Summary

The Streaming Response System makes DriftCache feel like a production LLM service:

✅ Real-time token streaming (ChatGPT-like UX)
✅ Server-Sent Events (SSE) standard
✅ Simultaneous streaming + collection
✅ Ready for cache integration
✅ Comprehensive error handling
✅ OpenAI SDK compatible

This is **production-grade streaming infrastructure** that sets the foundation for the semantic caching layer in Week 2.
