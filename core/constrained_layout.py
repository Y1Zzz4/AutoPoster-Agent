import math
from typing import List, Dict, Any
from core.state_context import PosterCard

def apply_constrained_layout(cards: List[PosterCard], canvas_width: float, canvas_height: float) -> Dict[str, Any]:
    if not cards:
        return {"heights": {}, "is_overflowing": False, "overflow_cards": []}

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
        return {"heights": {}, "is_overflowing": False, "overflow_cards": []}

    buckets = {"left_col": [], "mid_col": [], "right_col": []}
    col_w = canvas_width / 3.0
    margin = 25.0
    padding_base = 80.0 
    base_img_h = 380.0
    
    # dictionary
    metrics = {}

    # --- 1. culmulate Rigid and Flex height ---
    for card in body_cards:
        text_len = sum(len(b.content) for b in card.blocks if b.block_type == 'text')
        img_count = sum(1 for b in card.blocks if b.block_type == 'image')
    
        list_items = sum(b.content.count('<li>') for b in card.blocks if b.block_type == 'text')
        title_lines = math.ceil(len(card.title) / 25.0) 
        
        rigid_h = padding_base + (title_lines * 40.0) + (math.ceil(text_len / 45.0) * 32.0) + (list_items * 15.0)
        flex_h = img_count * base_img_h 
        
        metrics[card.card_id] = {"rigid": rigid_h, "flex": flex_h}
        card.token_weight = rigid_h + flex_h

    # --- 2. col、row ---
    if not any(c.is_zone_locked for c in body_cards):
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

    # --- 3. Rigid-Flex Mapping ---
    usable_col_h = canvas_height - header_h
    col_x_offsets = {"left_col": 0.0, "mid_col": col_w, "right_col": col_w * 2}
    actual_col_heights = {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}
    
    is_math_overflow = False
    overflow_card_ids = []

    for col_name, col_cards in buckets.items():
        if not col_cards: continue
        
        zx = col_x_offsets[col_name]
        current_y = header_h
        
        col_rigid_h = sum(metrics[c.card_id]["rigid"] for c in col_cards)
        col_flex_h = sum(metrics[c.card_id]["flex"] for c in col_cards)
        col_total_h = col_rigid_h + col_flex_h
        
        flex_scale = 1.0
        global_scale = 1.0
        
        if col_total_h > usable_col_h:
            overflow_amount = col_total_h - usable_col_h
            
            # judgement
            if overflow_amount > col_flex_h * 0.8:
                is_math_overflow = True
                heaviest_card = max(col_cards, key=lambda c: metrics[c.card_id]["rigid"])
                overflow_card_ids.append(heaviest_card.card_id)
                flex_scale = 0.2 if col_flex_h > 0 else 1.0
                global_scale = usable_col_h / col_total_h 
            else:
                # only compress height
                flex_scale = (col_flex_h - overflow_amount) / col_flex_h
        
        for card in col_cards:
            if is_math_overflow and col_flex_h == 0:
                final_card_h = metrics[card.card_id]["rigid"] * global_scale
            else:
                final_card_h = metrics[card.card_id]["rigid"] + (metrics[card.card_id]["flex"] * flex_scale)
                
            final_card_h = max(final_card_h, padding_base + 50.0)
            card.coordinates = [zx + margin, current_y + margin, col_w - 2 * margin, final_card_h - 2 * margin]
            current_y += final_card_h
            actual_col_heights[col_name] += final_card_h
            
    return {
        "heights": actual_col_heights, 
        "is_overflowing": is_math_overflow, 
        "overflow_cards": overflow_card_ids
    }