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
        self.model_name = "deepseek-chat"

    def _ensure_safe_css(self, styles: Dict[str, str]) -> Dict[str, str]:
        """
        Defensive programming contract: Ensures injected CSS does not violate 
        the rigid-flex geometrical constraints calculated by the Cartesian engine.
        """
        safe_styles = {}
        # 仅允许视觉修饰类属性，严禁注入尺寸、边距等物理属性
        allowed_properties = {
            'background-color', 'color', 'border', 'border-left', 
            'border-bottom', 'border-top', 'border-right', 
            'box-shadow', 'font-weight', 'border-radius'
        }
        
        if not isinstance(styles, dict):
            return safe_styles
            
        for k, v in styles.items():
            k_lower = k.lower().strip()
            if k_lower in allowed_properties:
                safe_styles[k_lower] = str(v).replace(';', '') # 净化输入
        return safe_styles

    async def plan_layout(self, state: SystemState) -> None:
        system_logger.info(f"[PlannerAgent] Computing spatial and stylistic mapping for Iteration {state.current_iteration + 1}.")

        cards_data = [
            {"card_id": c.card_id, "title": c.title, "current_weight": c.token_weight}
            for c in state.cards
        ]

        sys_prompt = (
            "You are an expert academic poster Art Director. Your task is to determine the spatial importance "
            "and visual salience for each semantic card based on the Scientific Editor's feedback.\n\n"
            "Rules:\n"
            "1. Output strictly valid JSON with a key 'layout_plan' containing a list of objects.\n"
            "2. Each object MUST have:\n"
            "   - 'card_id' (string)\n"
            "   - 'weight_multiplier' (float, default 1.0. Adjust up/down based on spatial feedback).\n"
            "   - 'custom_styles' (JSON object). Use ONLY these CSS properties to highlight core contributions: "
            "     background-color (e.g., '#f8f9fa' or '#fff0f0'), border-left (e.g., '4px solid #d32f2f'), box-shadow.\n"
            "3. If the Critic reports that a core result lacks visual salience, inject a highlight style for that specific card.\n"
            "4. DO NOT output any physical CSS like height, width, margin, or padding."
        )

        user_prompt = f"Current Semantic Cards:\n{json.dumps(cards_data, indent=2)}\n"

        if state.current_iteration > 0 and state.latest_feedback:
            user_prompt += (
                f"\nCRITICAL MULTI-MODAL FEEDBACK from Scientific Editor:\n"
                f"{json.dumps(state.latest_feedback, indent=2)}\n"
                "Apply appropriate 'weight_multiplier' and 'custom_styles' to resolve these issues."
            )

        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            plan_json = json.loads(response.choices[0].message.content)
            layout_plan = plan_json.get("layout_plan", [])

            for plan in layout_plan:
                cid = plan.get("card_id")
                target_card = next((c for c in state.cards if c.card_id == cid), None)
                if target_card:
                    # 1. Spatial weight update
                    multiplier = float(plan.get("weight_multiplier", 1.0))
                    multiplier = max(0.5, min(multiplier, 2.0))
                    target_card.token_weight *= multiplier
                    
                    # 2. Stylistic injection with defensive sanitization
                    raw_styles = plan.get("custom_styles", {})
                    target_card.custom_styles = self._ensure_safe_css(raw_styles)
                    
                    if target_card.custom_styles:
                        system_logger.info(f"  -> Applied stylistic injection to '{target_card.title}': {target_card.custom_styles}")

        except Exception as e:
            system_logger.error(f"[PlannerAgent] LLM parsing failed: {str(e)}. Retaining current state.")