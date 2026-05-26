import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class ContentBlock(BaseModel):
    """
    Data structure representing a single logical block of the poster.
    """
    block_id: str = Field(default_factory=lambda: f"block_{uuid.uuid4().hex[:8]}")
    block_type: str = Field(description="Type of content: 'text', 'image', or 'title'")
    content: str = Field(description="The actual text content or image path")
    token_weight: float = Field(default=1.0, description="Relative importance/size of this block")
    
    # Spatial coordinates [x, y, width, height], initialized as None
    coordinates: Optional[List[float]] = Field(default=None, description="Absolute coordinates in pixels")

class SystemState(BaseModel):
    """
    The global state machine tracking the context of a single generation task.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_document_path: str
    
    # Parsed assets
    content_blocks: List[ContentBlock] = Field(default_factory=list)
    
    # Iteration control for the feedback loop
    current_iteration: int = Field(default=0)
    max_iterations: int = Field(default=3)
    
    # Critic's feedback payload
    latest_feedback: Optional[Dict[str, Any]] = Field(default=None)
    
    # System flags
    is_converged: bool = Field(default=False, description="True if Critic approves the layout")
    is_fallback_triggered: bool = Field(default=False, description="True if max iterations reached")

    def get_block_by_id(self, block_id: str) -> Optional[ContentBlock]:
        """
        Retrieve a specific content block by its unique ID.
        """
        for block in self.content_blocks:
            if block.block_id == block_id:
                return block
        return None