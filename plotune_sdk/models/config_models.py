import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal, List, Any

class ExtensionConfig(BaseModel):
    name: str
    id: str
    version: str
    description: str
    mode:str # online, offline, hybrit
    author: str
    cmd: List[str]
    enabled: bool
    last_updated: str
    git_path: str
    category:str
    post_url: str
    webpage:Optional[str]
    file_formats: List[str]
    ask_form: bool
    connection: Dict[str, Any]
    configuration: Dict[str, Any]