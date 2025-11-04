import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal, List

class Variable(BaseModel):
    name:str
    source_ip:str
    source_port:int

class NewVariable(BaseModel):
    ref_variables:List[Variable]
    expr:str