import json
import base64
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class CriticAgent:
    """
    Scientific Editor Critic:
    Evaluates the rendered layout for Academic Emphasis, Visual Hierarchy, and Reading Flow.
    Physical collision checking is obsolete due to the deterministic layout engine.
    """
    def __init__(self):
        self.vision_client = api_client.critic_client
        self.model_name = "qwen3.6-plus"

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"

    async def evaluate_layout(self, state: SystemState, image_path: str) -> bool:
        """
        Executes a Vision-Language Model review focusing on scientific storytelling.
        """
        system_logger.info("CriticAgent (Scientific Editor) initiating evaluation of visual hierarchy...")
        base64_image = self._encode_image(image_path)

        # Extract the logical structure to guide the VLM's expectations
        expected_structure = [f"ID {c.card_id}: {c.title}" for c in state.cards]

        sys_prompt = (
            "You are an elite Scientific Chief Editor reviewing an academic poster. "
            "The layout engine has already mathematically guaranteed NO text overflow or overlap. "
            "Do NOT report physical clipping or formatting errors.\n\n"
            "Your objective is to evaluate the Scientific Communication Quality based on:\n"
            "1. Academic Emphasis: Are the core contributions ('Methodology', 'Results', 'Experiments') "
            "visually prominent? If 'Introduction' or 'Background' takes up more space than the results, this is a flaw.\n"
            "2. Visual Hierarchy: Are the key scientific figures and charts large enough to be the focal point of the column?\n"
            "3. Reading Flow: Does the layout guide the eye logically?\n\n"
            "Rules for Approval:\n"
            "- If the core results are prominent and the visual balance is acceptable, mark as PERFECT.\n"
            "- Do not be overly pedantic. Only flag severe hierarchy imbalances.\n\n"
            "Output strictly valid JSON. Format:\n"
            "{\n"
            "  \"analysis\": \"Analyze the space allocation. Which section dominates? Is it appropriate?\",\n"
            "  \"issues\": [{\"card_id\": \"target_card_id\", \"description\": \"Actionable advice, e.g., 'Increase weight for Results to enlarge charts' or 'Decrease weight for Introduction'\"}],\n"
            "  \"is_perfect\": boolean\n"
            "}"
        )

        user_prompt = f"Expected Semantic Flow:\n{expected_structure}\n\nExamine the poster image and provide your editorial review."

        try:
            response = await self.vision_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": base64_image}}
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            feedback_json: Dict[str, Any] = json.loads(response.choices[0].message.content)
            
            analysis_text = feedback_json.get("analysis", "No analysis provided.")
            system_logger.info(f"Editorial Analysis: {analysis_text}")
            
            issues = feedback_json.get("issues", [])
            is_perfect = feedback_json.get("is_perfect", False)

            if not issues:
                is_perfect = True

            # Important: We APPEND to latest_feedback, because the physical layout engine 
            # might have already injected 'squashed_cards' issues before the Critic runs.
            if state.latest_feedback and "issues" in state.latest_feedback:
                state.latest_feedback["issues"].extend(issues)
            else:
                state.latest_feedback = {"issues": issues}
            
            for issue in issues:
                system_logger.warning(f"Editorial Issue Detected: {issue}")

            return is_perfect

        except Exception as e:
            system_logger.error(f"CriticAgent evaluation failed: {str(e)}")
            return False