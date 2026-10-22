"""
OpenAI-compatible request/response schemas
"""
from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field


# Chat Completion Request Models
class Message(BaseModel):
    """Chat message"""
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    """Supported text-only chat completion request; reject unsupported features."""
    model_config = ConfigDict(extra="forbid")

    model: str
    messages: List[Message]
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    user: Optional[str] = None

    def generation_parameters(self) -> Dict[str, Any]:
        """Return response-affecting parameters used for cache compatibility."""
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens or 1024,
            "top_p": self.top_p,
            "stop": self.stop,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
        }


# Chat Completion Response Models
class UsageInfo(BaseModel):
    """Token usage information"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatMessage(BaseModel):
    """Chat message in response"""
    role: str
    content: str


class ChatCompletionChoice(BaseModel):
    """Individual completion choice"""
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response"""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: UsageInfo


# Streaming Response Models
class DeltaMessage(BaseModel):
    """Incremental message content for streaming"""
    role: Optional[str] = None
    content: Optional[str] = None


class ChatCompletionStreamChoice(BaseModel):
    """Streaming completion choice"""
    index: int
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionStreamResponse(BaseModel):
    """OpenAI-compatible streaming response chunk"""
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionStreamChoice]


# Models List Response
class ModelInfo(BaseModel):
    """Model information"""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsListResponse(BaseModel):
    """List of available models"""
    object: str = "list"
    data: List[ModelInfo]


# Error Response
class ErrorDetail(BaseModel):
    """Error detail"""
    message: str
    type: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response"""
    error: ErrorDetail
