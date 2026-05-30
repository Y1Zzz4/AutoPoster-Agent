from typing import List
from core.state_context import ContentBlock

def apply_constrained_layout(blocks: List[ContentBlock], canvas_width: float, canvas_height: float) -> None:
    """
    Applies a strict academic poster template: Top Header (15%) + Two Vertical Columns (85%).
    Blocks must be pre-assigned to 'header', 'left_col', or 'right_col' via PlannerAgent.
    """
    # 1. Define strict zone boundaries [x, y, w, h]
    header_h = canvas_height * 0.15
    col_w = canvas_width * 0.5
    col_h = canvas_height * 0.85
    
    zones = {
        "header": [0.0, 0.0, canvas_width, header_h],
        "left_col": [0.0, header_h, col_w, col_h],
        "right_col": [col_w, header_h, col_w, col_h]
    }
    
    # 2. Group blocks by their LLM-assigned zones
    zone_blocks = {"header": [], "left_col": [], "right_col": []}
    
    # Default fallback assignment if 'zone_id' is missing
    for block in blocks:
        target_zone = getattr(block, 'zone_id', 'left_col') 
        if target_zone in zone_blocks:
            zone_blocks[target_zone].append(block)
            
    # 3. Apply 1D vertical stacking within each zone
    margin = 20.0
    for zone_name, rect in zones.items():
        z_blocks = zone_blocks[zone_name]
        if not z_blocks:
            continue
            
        zx, zy, zw, zh = rect
        total_weight = sum(b.token_weight for b in z_blocks)
        current_y = zy
        
        for b in z_blocks:
            # Calculate height proportional to block's token weight
            block_h = zh * (b.token_weight / total_weight) if total_weight > 0 else 0
            
            # Inject coordinates with margins applied
            b.coordinates = [
                zx + margin, 
                current_y + margin, 
                zw - 2 * margin, 
                block_h - 2 * margin
            ]
            current_y += block_h