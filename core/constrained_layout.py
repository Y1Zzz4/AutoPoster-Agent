from typing import List
from core.state_context import PosterCard

def apply_constrained_layout(cards: List[PosterCard], canvas_width: float, canvas_height: float) -> None:
    """
    [P2P Greedy Masonry Algorithm]
    Dynamically balances cards across 3 columns to prevent empty spaces.
    """
    header_h = canvas_height * 0.12
    col_w = canvas_width / 3.0
    margin = 25.0
    
    # Track the current Y-coordinate (height) of each column
    col_heights = {
        "left_col": header_h,
        "mid_col": header_h,
        "right_col": header_h
    }
    
    col_x_offsets = {
        "left_col": 0.0,
        "mid_col": col_w,
        "right_col": col_w * 2
    }
    
    # 1. 强制放置 Header
    header_card = cards[0]
    header_card.zone_id = "header"
    header_card.coordinates = [0.0, 0.0, canvas_width, header_h]
    
    # 2. 瀑布流分配其余卡片
    body_cards = cards[1:]
    # Calculate a global weight-to-pixel ratio to determine raw card heights
    total_weight = sum(c.token_weight for c in body_cards)
    usable_total_height = (canvas_height - header_h) * 3.0 # 3 columns of usable space
    
    for card in body_cards:
        # Find the currently shortest column
        shortest_col = min(col_heights, key=col_heights.get)
        
        # Calculate optimal height based on token ratio
        card_h = (card.token_weight / total_weight) * usable_total_height if total_weight > 0 else 200.0
        
        # Enforce minimum height to prevent overflow
        card_h = max(card_h, 250.0)
        
        zx = col_x_offsets[shortest_col]
        zy = col_heights[shortest_col]
        
        card.zone_id = shortest_col
        card.coordinates = [
            zx + margin, 
            zy + margin, 
            col_w - 2 * margin, 
            card_h - 2 * margin
        ]
        
        # Update the column's height
        col_heights[shortest_col] += card_h