import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ExtensionConfig(BaseModel):
    """Configuration model for a Plotune extension."""

    name: str
    id: str
    version: str
    description: str
    mode: str  # allowed values: "online", "offline", "hybrid"
    author: str
    cmd: List[str]
    enabled: bool
    last_updated: str
    git_path: str
    category: str
    post_url: str
    webpage: Optional[str]
    file_formats: List[str]
    ask_form: bool
    connection: Dict[str, Any]
    configuration: Dict[str, Any]
