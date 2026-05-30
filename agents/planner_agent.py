import json
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class PlannerAgent:
    """
    Determines the spatial importance (weight multipliers) for PosterCards.
    Strictly preserves the original academic reading order.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-chat"

    async def plan_layout(self, state: SystemState) -> None:
        system_logger.info(f"Iteration {state.current_iteration}: Requesting layout plan from LLM.")

        cards_data = [
            {"card_id": c.card_id, "title": c.title, "current_weight": c.token_weight}
            for c in state.cards
        ]

        system_prompt = (
            "You are an expert academic poster designer. Your ONLY task is to determine the "
            "spatial importance (weight_multiplier) for each semantic card.\n\n"
            "Rules:\n"
            "1. Output strictly valid JSON with a key 'layout_plan' containing a list of objects.\n"
            "2. Each object MUST have 'card_id', 'reasoning', and 'weight_multiplier' (float, default 1.0).\n"
            "3. DO NOT change the original sequence. The academic flow MUST be preserved.\n"
            "4. Assign higher multipliers (1.5 to 2.5) to core sections like 'Methodology' or 'Results' "
            "so they receive more physical canvas space."
        )

        user_prompt = f"Here are the semantic cards:\n{json.dumps(cards_data, indent=2)}\n"

        if state.current_iteration > 0 and state.latest_feedback:
            user_prompt += (
                f"\nCRITICAL FEEDBACK from previous iteration:\n"
                f"{json.dumps(state.latest_feedback, indent=2)}\n"
                "Adjust 'weight_multiplier' to fix visual errors (e.g., increase multiplier if text overflows)."
            )

        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1 
            )

            plan_json = json.loads(response.choices[0].message.content)
            self._apply_plan_to_state(plan_json, state)

        except Exception as e:
            system_logger.error(f"Failed to generate/parse LLM plan: {str(e)}")

    def _apply_plan_to_state(self, plan_json: Dict[str, Any], state: SystemState) -> None:
        """
        Updates card weights in-place with strict anti-erosion clamping.
        """
        layout_list = plan_json.get("layout_plan", [])
        
        multiplier_map = {
            item.get("card_id"): float(item.get("weight_multiplier", 1.0)) 
            for item in layout_list
        }

        for card in state.cards:
            if card.card_id in multiplier_map:
                multiplier = multiplier_map[card.card_id]
                
                clamped_multiplier = max(0.5, min(multiplier, 2.0)) 
                
                card.token_weight = max(card.token_weight * clamped_multiplier, 80.0)