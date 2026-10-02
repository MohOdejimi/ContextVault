from pydantic import BaseModel, ConfigDict
from datetime import datetime

class Document_Response(BaseModel):
    id: int
    original_filename: str
    content_type: str
    size_in_bytes: int
    processing_state: str
    created_at: datetime
    model_config=ConfigDict(from_attributes=True)