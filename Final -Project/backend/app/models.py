from typing import Dict, Any
from pydantic import BaseModel, field_validator

class NoteCreate(BaseModel):
    content: str
    action: str = "save"
    
    @field_validator('content')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v.strip()

class VerifyUpdate(BaseModel):
    human_data: Dict[str, Any]

