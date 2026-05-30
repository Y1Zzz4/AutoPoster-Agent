import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class ContentBlock(BaseModel):
    """Represents a discrete piece of content (text or image)."""
    block_type: str 
    content: str 

class PosterCard(BaseModel):
    """
    [P2P Upgrade]: A Semantic Card representing a full section (e.g., 'Methodology').
    It groups a section title, summarized text, and its relevant images together.
    """
    card_id: str = Field(default_factory=lambda: f"card_{uuid.uuid4().hex[:8]}")
    title: str = Field(default="Section")
    blocks: List[ContentBlock] = Field(default_factory=list)
    
    # Card physical properties
    token_weight: float = Field(default=0.0)
    zone_id: str = Field(default="left_col") # 'header', 'left_col', 'mid_col', 'right_col'
    coordinates: Optional[List[float]] = Field(default=None)

class SystemState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_document_path: str
    document_name: str = Field(default="default_doc")
    
    # [UPDATE]: The system now manages Cards, not isolated blocks
    cards: List[PosterCard] = Field(default_factory=list)
    
    current_iteration: int = Field(default=0)
    max_iterations: int = Field(default=5)
    latest_feedback: Optional[Dict[str, Any]] = Field(default=None)
    is_converged: bool = Field(default=False)
    is_fallback_triggered: bool = Field(default=False)