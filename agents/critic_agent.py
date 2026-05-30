import json
import base64
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class CriticAgent:
    """
    Evaluates the rendered layout strictly for physical collisions and overflow constraints.
    """
    def __init__(self):
        self.vision_client = api_client.critic_client
        self.model_name = "qwen-vl-max"

    def _encode_image(self, image_path: str) -> str:
        """
        Encodes the rendered screenshot to base64 for API transmission.
        """
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"

    async def evaluate_layout(self, state: SystemState, image_path: str) -> bool:
        """
        Executes a Vision-Language Model review against strict rendering constraints.
        """
        system_logger.info("CriticAgent initiating visual inspection of current layout.")

        base64_image = self._encode_image(image_path)

        sys_prompt = (
            "You are an objective computer vision layout inspector. Your task is to detect critical rendering "
            "failures in the provided academic poster.\n\n"
            "Evaluation Rules:\n"
            "1. IGNORE whitespace at the bottom of the poster. Uneven column heights are INTENTIONAL.\n"
            "2. Report a physical 'issue' ONLY under these conditions:\n"
            "   - Text visibly overflows outside its assigned white card boundary.\n"
            "   - Two cards overlap or collide with each other.\n"
            "   - Images clip outside their card containers.\n"
            "   - The main header text is cut off or illegible.\n"
            "3. Output strictly valid JSON. Format:\n"
            "   {\"issues\": [{\"card_id\": \"id_if_visible\", \"description\": \"specific physical error\"}], \"is_perfect\": boolean}"
        )

        user_prompt = "Examine this layout and return the JSON evaluation."

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
                temperature=0.0
            )

            feedback_json: Dict[str, Any] = json.loads(response.choices[0].message.content)
            
            issues = feedback_json.get("issues", [])
            is_perfect = feedback_json.get("is_perfect", False)

            if not issues:
                is_perfect = True

            state.latest_feedback = {"issues": issues}
            
            for issue in issues:
                system_logger.warning(f"Visual Defect Detected: {issue}")

            return is_perfect

        except Exception as e:
            system_logger.error(f"CriticAgent evaluation failed: {str(e)}")
            state.latest_feedback = {"issues": [{"card_id": "unknown", "description": "Vision API failure"}]}
            return False