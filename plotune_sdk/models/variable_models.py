import uuid
from datetime import datetime
from typing import Optional, Dict, Literal, List

from pydantic import BaseModel, Field


class Variable(BaseModel):
    """Represents a variable with source information."""
    name: str
    source_ip: str
    source_port: int


class NewVariable(BaseModel):
    """Represents a new variable defined via expression using reference variables."""
    ref_variables: List[Variable]
    expr: str
