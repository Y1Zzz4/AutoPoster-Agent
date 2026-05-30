from typing import List
from core.state_context import PosterCard

def apply_constrained_layout(cards: List[PosterCard], canvas_width: float, canvas_height: float) -> dict:
    """
    Applies Locked-Column Layout & Natural Height Downscaling.
    Returns a dictionary of the actual heights of each column for aesthetic evaluation.
    """
    if not cards:
        return {}

    # --- 1. Header Logic ---
    header_card = cards[0]
    title_length = len(header_card.title)
    
    # Give the header breathing room based on title length
    extra_ratio = max(0, (title_length - 40) // 30) * 0.05
    header_ratio = min(0.12 + extra_ratio, 0.22)
    header_h = canvas_height * header_ratio
    
    header_card.zone_id = "header"
    header_card.is_zone_locked = True
    header_card.coordinates = [0.0, 0.0, canvas_width, header_h]
    
    body_cards = cards[1:]
    if not body_cards:
        return {}

    # --- 2. Zone Assignment (Executed ONLY on Iteration 0) ---
    buckets = {"left_col": [], "mid_col": [], "right_col": []}
    
    if not any(c.is_zone_locked for c in body_cards):
        # Initialization: Distribute cards sequentially based on raw pixel weight
        total_weight = sum(c.token_weight for c in body_cards)
        target_bucket_weight = total_weight / 3.0
        
        bucket_names = list(buckets.keys())
        current_idx = 0
        current_weight = 0.0
        
        for card in body_cards:
            if current_idx < 2 and (current_weight + card.token_weight * 0.6) > target_bucket_weight:
                current_idx += 1
                current_weight = 0.0
            
            target_col = bucket_names[current_idx]
            card.zone_id = target_col
            card.is_zone_locked = True # Lock it permanently!
            current_weight += card.token_weight
            buckets[target_col].append(card)
    else:
        # Subsequent Iterations: Strictly follow locked zones
        for card in body_cards:
            # Fallback for safety
            zone = card.zone_id if card.zone_id in buckets else "left_col"
            buckets[zone].append(card)

    # --- 3. Natural Height Calculation & Overflow Protection ---
    col_w = canvas_width / 3.0
    usable_col_h = canvas_height - header_h
    margin = 25.0
    
    col_x_offsets = {"left_col": 0.0, "mid_col": col_w, "right_col": col_w * 2}
    actual_col_heights = {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}
    
    for col_name, col_cards in buckets.items():
        if not col_cards:
            continue
            
        zx = col_x_offsets[col_name]
        current_y = header_h
        
        # Calculate raw requested height based on LLM multiplier
        raw_total_h = sum(c.token_weight for c in col_cards)
        
        # Scale down ONLY if the column overflows the canvas. 
        # If it's shorter, scale_factor = 1.0 (prevents massive whitespace inside cards)
        scale_factor = usable_col_h / raw_total_h if raw_total_h > usable_col_h else 1.0
        
        for card in col_cards:
            final_h = card.token_weight * scale_factor
            
            card.coordinates = [
                zx + margin, 
                current_y + margin, 
                col_w - 2 * margin, 
                final_h - 2 * margin
            ]
            current_y += final_h
            actual_col_heights[col_name] += final_h

    # Return heights to the Pipeline for aesthetic variance calculation
    return actual_col_heights