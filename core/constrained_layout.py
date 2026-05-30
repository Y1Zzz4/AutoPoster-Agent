import math
from typing import List, Dict
from core.state_context import PosterCard

def apply_constrained_layout(cards: List[PosterCard], canvas_width: float, canvas_height: float) -> Dict[str, float]:
    """
    Applies a bottom-up rigid content height estimation combined with a top-down constraint mapping.
    Strictly preserves locked column positioning and mathematically prevents content clipping.
    
    Args:
        cards (List[PosterCard]): List of semantic poster cards partitioned from Markdown.
        canvas_width (float): Total width of the poster canvas in pixels (e.g., 1920).
        canvas_height (float): Total height of the poster canvas in pixels (e.g., 1080).
        
    Returns:
        Dict[str, float]: Actual accumulated heights of the columns for aesthetic loss evaluation.
    """
    if not cards:
        return {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}

    # --- Step 1: Dynamic Smooth Header Scaling ---
    header_card = cards[0]
    title_len = len(header_card.title)
    
    # Calculate float-based scale ratio to avoid block-clipping on multi-line text wrapper
    extra_ratio = max(0.0, (title_len - 25) / 25.0) * 0.04
    header_ratio = min(0.12 + extra_ratio, 0.26)
    header_h = canvas_height * header_ratio
    
    header_card.zone_id = "header"
    header_card.is_zone_locked = True
    header_card.coordinates = [0.0, 0.0, canvas_width, header_h]
    
    body_cards = cards[1:]
    if not body_cards:
        return {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}

    # --- Step 2: Absolute Column Anchor Locking (Anti-Oscillation) ---
    buckets = {"left_col": [], "mid_col": [], "right_col": []}
    col_w = canvas_width / 3.0
    margin = 25.0
    usable_col_w = col_w - 2 * margin # Exact width inside a card container (~590px)
    
    # Estimate characters per line based on font sizing and card width constraints
    # At font-size 1.3rem (~21px), a 590px container holds ~45 English alphanumeric characters per line.
    chars_per_line = 45.0 
    line_h = 32.0 # Line height in pixels including line-spacing (1.6)
    padding_base = 80.0 # Top + bottom container padding and gaps inside the card

    # Step 2.1: First-time initialization pass
    if not any(c.is_zone_locked for c in body_cards):
        # Calculate raw physical height request for each card before allocation
        for card in body_cards:
            text_len = sum(len(b.content) for b in card.blocks if b.block_type == 'text')
            img_count = sum(1 for b in card.blocks if b.block_type == 'image')
            title_lines = math.ceil(len(card.title) / 25.0) # Section titles use larger font
            
            # Formulate the rigid physical height demand
            est_text_h = math.ceil(text_len / chars_per_line) * line_h
            est_title_h = title_lines * 40.0
            est_img_h = img_count * 380.0 # Reserve spatial bounding box for figures
            
            card.token_weight = padding_base + est_title_h + est_text_h + est_img_h
            
        # Distribute cards sequentially based on estimated pixel load
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
        # Step 2.2: Consistent feedback loops (Strictly maintain assigned arrays)
        for card in body_cards:
            target_col = card.zone_id if card.zone_id in buckets else "left_col"
            buckets[target_col].append(card)

    # --- Step 3: Top-Down Multi-Mode Geometrical Packing ---
    usable_col_h = canvas_height - header_h
    col_x_offsets = {"left_col": 0.0, "mid_col": col_w, "right_col": col_w * 2}
    actual_col_heights = {"left_col": 0.0, "mid_col": 0.0, "right_col": 0.0}
    
    for col_name, col_cards in buckets.items():
        if not col_cards:
            continue
            
        zx = col_x_offsets[col_name]
        current_y = header_h
        
        # Calculate the total physical height requested by this column's cards
        col_requested_h = sum(c.token_weight for c in col_cards)
        
        # Determine the scale scaling protocol to handle overflow vs underflow
        # Mode A (Overflow): Total height > viewport. Scale down everything proportionally.
        # Mode B (Underflow): Total height <= viewport. Keep natural heights to prevent text stretching.
        is_overflowing = col_requested_h > usable_col_h
        scale_factor = usable_col_h / col_requested_h if is_overflowing else 1.0
        
        for card in col_cards:
            # Map structural coordinate data
            final_card_h = card.token_weight * scale_factor
            
            # Safeguard constraint: Ensure box is never flattened below its padding threshold
            final_card_h = max(final_card_h, padding_base + 50.0)
            
            card.coordinates = [
                zx + margin,
                current_y + margin,
                col_w - 2 * margin,
                final_card_h - 2 * margin
            ]
            
            current_y += final_card_h
            actual_col_heights[col_name] += final_card_h
            
    return actual_col_heights