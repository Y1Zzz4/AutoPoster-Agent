import json
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class PlannerAgent:
    """
    Determines the optimal semantic reading order and weight multipliers for PosterCards.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"

    async def plan_layout(self, state: SystemState) -> None:
        """
        Generates a JSON plan ordering the cards and adjusting their area weights.
        """
        system_logger.info(f"Iteration {state.current_iteration}: Requesting layout plan from LLM.")

        cards_data = [
            {
                "card_id": c.card_id,
                "title": c.title,
                "current_weight": c.token_weight
            }
            for c in state.cards
        ]

        system_prompt = (
            "You are an expert academic poster designer. Your task is to determine the optimal "
            "reading order and spatial importance (weight_multiplier) for the given semantic cards.\n\n"
            "Rules:\n"
            "1. Output strictly valid JSON with a key 'layout_plan' containing a list of objects.\n"
            "2. Each object MUST have 'card_id', 'reasoning', and 'weight_multiplier' (float, default 1.0. Increase to 1.5+ for crucial charts).\n"
            "3. The order of the list determines the reading flow. The first card MUST be the Header.\n"
        )

        user_prompt = f"Here are the semantic cards:\n{json.dumps(cards_data, indent=2)}\n"

        if state.current_iteration > 0 and state.latest_feedback:
            user_prompt += (
                f"\nCRITICAL FEEDBACK from previous iteration:\n"
                f"{json.dumps(state.latest_feedback, indent=2)}\n"
                "Adjust 'weight_multiplier' or order to fix visual errors (e.g., increase multiplier if text overflows)."
            )

        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2 
            )

            plan_json = json.loads(response.choices[0].message.content)
            self._apply_plan_to_state(plan_json, state)

        except Exception as e:
            system_logger.error(f"Failed to generate/parse LLM plan: {str(e)}")

    def _apply_plan_to_state(self, plan_json: Dict[str, Any], state: SystemState) -> None:
        layout_list = plan_json.get("layout_plan", [])
        card_map = {c.card_id: c for c in state.cards}
        reordered_cards = []

        for item in layout_list:
            c_id = item.get("card_id")
            multiplier = float(item.get("weight_multiplier", 1.0))
            
            if c_id in card_map:
                card = card_map[c_id]
                card.token_weight = card.token_weight * multiplier
                reordered_cards.append(card)
                del card_map[c_id]
                
        for remaining_card in card_map.values():
            reordered_cards.append(remaining_card)
            
        state.cards = reordered_cards