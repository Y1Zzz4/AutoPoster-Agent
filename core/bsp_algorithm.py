from typing import List
from core.state_context import ContentBlock
from utils.logger import system_logger

def apply_bsp_layout(blocks: List[ContentBlock], canvas_width: float, canvas_height: float) -> None:
    """
    Main entry point for the Binary Space Partitioning (BSP) algorithm.
    It takes a list of ContentBlocks and directly mutates their 'coordinates' attribute.
    
    Args:
        blocks: List of parsed blocks from the document.
        canvas_width: The total width of the poster canvas in pixels.
        canvas_height: The total height of the poster canvas in pixels.
    """
    system_logger.info(f"Starting BSP layout for {len(blocks)} blocks on {canvas_width}x{canvas_height} canvas.")
    
    # Start the recursive division from the top-left corner (0, 0)
    _recursive_bsp(blocks, 0.0, 0.0, canvas_width, canvas_height)
    
    system_logger.info("BSP layout calculation completed successfully.")


def _recursive_bsp(blocks: List[ContentBlock], x: float, y: float, w: float, h: float) -> None:
    """
    Recursively divides the bounding box [x, y, w, h] among the given blocks 
    based on their relative 'token_weight'.
    """
    # Base Case 1: Empty list (safety check)
    if not blocks:
        return
        
    # Base Case 2: Only one block left. It occupies the entire current bounding box.
    if len(blocks) == 1:
        # Add a fixed margin (e.g., 20px) to prevent text/images from touching the borders
        margin = 20.0
        # Format: [x, y, width, height]
        blocks[0].coordinates = [x + margin, y + margin, w - 2 * margin, h - 2 * margin]
        return

    # 1. Calculate the total weight of the current subset of blocks
    total_weight = sum(block.token_weight for block in blocks)
    
    # 2. Divide the blocks into two halves (semantic grouping)
    # Note: In the next step, our PlannerAgent (DeepSeek) will pre-sort these blocks 
    # to ensure the splitting here makes semantic sense (e.g., Abstract on left, Images on right).
    mid_index = len(blocks) // 2
    left_blocks = blocks[:mid_index]
    right_blocks = blocks[mid_index:]
    
    # 3. Calculate the spatial ratio for the left/top partition
    left_weight = sum(block.token_weight for block in left_blocks)
    # Prevent division by zero
    split_ratio = left_weight / total_weight if total_weight > 0 else 0.5
    
    # 4. Determine split direction: Always split along the longer edge.
    # This prevents creating excessively thin and unreadable rectangular strips.
    if w > h:
        # Split Horizontally (Left and Right panels)
        left_w = w * split_ratio
        right_w = w - left_w
        
        # Recurse on the left panel
        _recursive_bsp(left_blocks, x, y, left_w, h)
        # Recurse on the right panel
        _recursive_bsp(right_blocks, x + left_w, y, right_w, h)
    else:
        # Split Vertically (Top and Bottom panels)
        top_h = h * split_ratio
        bottom_h = h - top_h
        
        # Recurse on the top panel
        _recursive_bsp(left_blocks, x, y, w, top_h)
        # Recurse on the bottom panel
        _recursive_bsp(right_blocks, x, y + top_h, w, bottom_h)