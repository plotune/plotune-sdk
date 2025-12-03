import uuid
from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, Field


class FileMetaData(BaseModel):
    """
    A detailed metadata model for a file.
    """
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="A unique identifier for the file metadata."
    )
    name: str = Field(..., description="The name of the file.")
    path: str = Field(..., description="The file path on the system.")
    source: str = Field(..., description="The source of the file.")
    headers: Optional[List[str]] = Field(
        None, description="A list of headers found in the file."
    )
    desc: Optional[str] = Field(None, description="A description of the file's content.")
    tags: Optional[List[str]] = Field(None, description="A list of tags for the file.")
    created_at: Optional[datetime] = Field(
        None, description="The creation timestamp of the file."
    )
    source_url: Optional[str] = Field(
        None, description="The URL from which the file was sourced."
    )


class FileReadRequest(BaseModel):
    """
    A model to request reading a single file.
    """
    mode: Literal["online", "offline"] = Field(
        ..., description="The reading mode, 'online' for a stream or 'offline' for a static read."
    )
    path: str = Field(..., description="The file path to be read.")
