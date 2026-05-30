import math
from typing import List, Dict, Any
from core.state_context import PosterCard

def apply_constrained_layout(cards: List[PosterCard], canvas_width: float, canvas_height: float) -> Dict[str, Any]:
    """
    Executes bottom-up height estimation and top-down packing.
    Returns column heights and a list of card IDs that violate the image legibility threshold.
    """
    if not cards:
        return {"heights": {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}, "squashed_cards": []}

    header_card = cards[0]
    title_len = len(header_card.title)
    
    extra_ratio = max(0.0, (title_len - 25) / 25.0) * 0.04
    header_ratio = min(0.12 + extra_ratio, 0.26)
    header_h = canvas_height * header_ratio
    
    header_card.zone_id = "header"
    header_card.is_zone_locked = True
    header_card.coordinates = [0.0, 0.0, canvas_width, header_h]
    
    body_cards = cards[1:]
    if not body_cards:
        return {"heights": {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}, "squashed_cards": []}

    buckets = {"left_col": [], "mid_col": [], "right_col": []}
    col_w = canvas_width / 3.0
    margin = 25.0
    
    chars_per_line = 45.0 
    line_h = 32.0 
    padding_base = 80.0 
    base_img_h = 380.0
    legibility_threshold = 220.0 # Minimum recognizable height for an academic figure

    if not any(c.is_zone_locked for c in body_cards):
        for card in body_cards:
            text_len = sum(len(b.content) for b in card.blocks if b.block_type == 'text')
            img_count = sum(1 for b in card.blocks if b.block_type == 'image')
            title_lines = math.ceil(len(card.title) / 25.0) 
            
            est_text_h = math.ceil(text_len / chars_per_line) * line_h
            est_title_h = title_lines * 40.0
            est_img_h = img_count * base_img_h 
            
            card.token_weight = padding_base + est_title_h + est_text_h + est_img_h
            
        total_estimated_h = sum(c.token_weight for c in body_cards)
        target_bucket_h = total_estimated_h / 3.0
        
        bucket_names = list(buckets.keys())
        current_idx = 0
        current_accumulated_h = 0.0
        
        for card in body_cards:
            if current_idx < 2 and (current_accumulated_h + card.token_weight * 0.65) > target_bucket_h:
                current_idx += 1
                current_accumulated_h = 0.0
                
            target_col = bucket_names[current_idx]
            card.zone_id = target_col
            card.is_zone_locked = True
            current_accumulated_h += card.token_weight
            buckets[target_col].append(card)
    else:
        for card in body_cards:
            target_col = card.zone_id if card.zone_id in buckets else "left_col"
            buckets[target_col].append(card)

    usable_col_h = canvas_height - header_h
    col_x_offsets = {"left_col": 0.0, "mid_col": col_w, "right_col": col_w * 2}
    actual_col_heights = {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}
    squashed_cards = []
    
    for col_name, col_cards in buckets.items():
        if not col_cards:
            continue
            
        zx = col_x_offsets[col_name]
        current_y = header_h
        
        col_requested_h = sum(c.token_weight for c in col_cards)
        is_overflowing = col_requested_h > usable_col_h
        scale_factor = usable_col_h / col_requested_h if is_overflowing else 1.0
        
        for card in col_cards:
            # Check image legibility violation mathematically
            img_count = sum(1 for b in card.blocks if b.block_type == 'image')
            if img_count > 0:
                projected_img_h = base_img_h * scale_factor
                if projected_img_h < legibility_threshold:
                    squashed_cards.append(card.card_id)

            final_card_h = card.token_weight * scale_factor
            final_card_h = max(final_card_h, padding_base + 50.0)
            
            card.coordinates = [
                zx + margin,
                current_y + margin,
                col_w - 2 * margin,
                final_card_h - 2 * margin
            ]
            
            current_y += final_card_h
            actual_col_heights[col_name] += final_card_h
            
    return {"heights": actual_col_heights, "squashed_cards": squashed_cards}