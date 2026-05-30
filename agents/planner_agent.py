import json
from typing import Dict, Any, List
from core.state_context import SystemState, PosterCard
from utils.api_client import api_client
from utils.logger import system_logger

class PlannerAgent:
    """
    MIMO Controller: Computes spatial weights (geometric constraints) 
    and semantic style overrides (visual rendering) based on Critic feedback.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"

    def _ensure_safe_css(self, styles: Dict[str, str]) -> Dict[str, str]:
        safe_styles = {}
        allowed_properties = {'background-color', 'color', 'font-weight'}
        if isinstance(styles, dict):
            for k, v in styles.items():
                k_lower = k.lower().strip()
                if k_lower in allowed_properties:
                    safe_styles[k_lower] = str(v).replace(';', '')
        return safe_styles

    async def plan_layout(self, state: SystemState) -> None:
        system_logger.info(f"[PlannerAgent] Computing spatial weights, CSS, and Semantic Pagination.")

        cards_data = [
            {"card_id": c.card_id, "title": c.title, "current_weight": c.token_weight, "current_zone": c.zone_id}
            for c in state.cards[1:]
        ]

        sys_prompt = (
            "You are an expert academic poster Art Director. You decide spatial weights, styles, and COLUMN ALLOCATION.\n\n"
            "Rules for 'layout_plan' JSON objects:\n"
            "1. 'card_id': strictly matching the input.\n"
            "2. 'zone_id': You MUST assign each card to 'left_col', 'mid_col', or 'right_col'.\n"
            "   CRITICAL: The academic reading flow MUST be monotonic. Cards must flow strictly from left to right. "
            "   (e.g., Abstract in left, Method in mid, Results in right).\n"
            "3. 'weight_multiplier': float (default 1.0).\n"
            "4. 'custom_styles': JSON object for highlighting.\n"
        )

        user_prompt = f"Semantic Cards:\n{json.dumps(cards_data, indent=2)}\n"

        if state.current_iteration > 0 and state.latest_feedback:
            user_prompt += (
                f"\nCRITICAL FEEDBACK from Scientific Editor:\n"
                f"{json.dumps(state.latest_feedback, indent=2)}\n"
                "Re-allocate 'zone_id' or adjust weights/styles to resolve pagination and visual issues."
            )

        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            plan_json = json.loads(response.choices[0].message.content)
            layout_plan = plan_json.get("layout_plan", [])
            
            zone_mapping = {plan.get("card_id"): plan.get("zone_id", "left_col") for plan in layout_plan}
            
            # Monotonicity Enforcement
            valid_zones = {"left_col": 0, "mid_col": 1, "right_col": 2}
            reverse_zones = {0: "left_col", 1: "mid_col", 2: "right_col"}
            current_z_val = 0
            
            for card in state.cards:
                if card.zone_id == "header":
                    continue
                    
                target_zone = zone_mapping.get(card.card_id, "left_col")
                z_val = valid_zones.get(target_zone, current_z_val)
                
                if z_val < current_z_val:
                    z_val = current_z_val
                current_z_val = z_val
                
                card.zone_id = reverse_zones[z_val]

            for plan in layout_plan:
                cid = plan.get("card_id")
                target_card = next((c for c in state.cards if c.card_id == cid), None)
                if target_card:
                    multiplier = max(0.5, min(float(plan.get("weight_multiplier", 1.0)), 2.0))
                    target_card.token_weight *= multiplier
                    target_card.custom_styles = self._ensure_safe_css(plan.get("custom_styles", {}))

        except Exception as e:
            system_logger.error(f"[PlannerAgent] LLM parsing failed: {str(e)}.")
            for card in state.cards:
                if card.zone_id == "unassigned": card.zone_id = "left_col"