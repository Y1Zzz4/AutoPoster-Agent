from typing import List
from core.state_context import ContentBlock

def apply_constrained_layout(blocks: List[ContentBlock], canvas_width: float, canvas_height: float) -> None:
    """
    Applies a classic 3-column academic poster template (Landscape).
    Top Header (12%) + Three Vertical Columns (88%).
    """
    header_h = canvas_height * 0.12
    col_w = canvas_width / 3.0  # Divide canvas into 3 equal columns
    col_h = canvas_height * 0.88
    
    zones = {
        "header": [0.0, 0.0, canvas_width, header_h],
        "left_col": [0.0, header_h, col_w, col_h],
        "mid_col": [col_w, header_h, col_w, col_h],
        "right_col": [col_w * 2, header_h, col_w, col_h]
    }
    
    zone_blocks = {"header": [], "left_col": [], "mid_col": [], "right_col": []}
    
    for block in blocks:
        target_zone = getattr(block, 'zone_id', 'left_col') 
        if target_zone not in zones: 
            target_zone = 'left_col' # Fallback for hallucinated zones
        zone_blocks[target_zone].append(block)
            
    margin = 25.0 # Slightly larger margin for landscape readability
    for zone_name, rect in zones.items():
        z_blocks = zone_blocks[zone_name]
        if not z_blocks:
            continue
            
        zx, zy, zw, zh = rect
        total_weight = sum(b.token_weight for b in z_blocks)
        current_y = zy
        
        for b in z_blocks:
            block_h = zh * (b.token_weight / total_weight) if total_weight > 0 else 0
            b.coordinates = [
                zx + margin, 
                current_y + margin, 
                zw - 2 * margin, 
                block_h - 2 * margin
            ]
            current_y += block_h