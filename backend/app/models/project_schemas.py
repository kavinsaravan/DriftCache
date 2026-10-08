"""Request and response schemas for project credentials."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    key_name: str = Field(default="default", min_length=1, max_length=100)


class ProjectKeyCreate(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=100)


class ProjectCredentialResponse(BaseModel):
    project_id: str
    project_name: str
    tenant_id: str
    api_key_id: str
    api_key_name: str
    api_key: str
    created_at: datetime
    warning: str = "Store this key securely. It cannot be retrieved again."


class ProjectKeyResponse(BaseModel):
    project_id: str
    api_key_id: str
    api_key_name: str
    api_key: str
    created_at: datetime
    warning: str = "Store this key securely. It cannot be retrieved again."


class ProjectKeySummary(BaseModel):
    id: str
    project_id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ProjectSummary(BaseModel):
    id: str
    name: str
    tenant_id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
