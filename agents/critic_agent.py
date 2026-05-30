import json
import base64
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class CriticAgent:
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
        Terminal logging for detailed analysis has been suppressed.
        """
        base64_image = self._encode_image(image_path)
        expected_structure = [f"ID {c.card_id}: {c.title}" for c in state.cards]

        sys_prompt = (
            "You are an elite Scientific Chief Editor reviewing an academic poster. "
            "The layout engine has already mathematically guaranteed NO text overflow or overlap. "
            "Do NOT report physical clipping or formatting errors.\n\n"
            "Your objective is to evaluate the Scientific Communication Quality based on:\n"
            "1. Academic Emphasis: Are the core contributions visually prominent?\n"
            "2. Visual Hierarchy: Are the key scientific figures and charts large enough?\n"
            "3. Reading Flow: Does the layout guide the eye logically?\n\n"
            "Output strictly valid JSON. Format:\n"
            "{\n"
            "  \"analysis\": \"Analyze the space allocation.\",\n"
            "  \"issues\": [{\"card_id\": \"target_card_id\", \"description\": \"Actionable advice\"}],\n"
            "  \"is_perfect\": boolean\n"
            "}"
        )

        user_prompt = f"Expected Semantic Flow:\n{expected_structure}\n\nExamine the poster image and provide your editorial review."

        try:
            response = await self.vision_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}, {"type": "image_url", "image_url": {"url": base64_image}}]}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            feedback_json: Dict[str, Any] = json.loads(response.choices[0].message.content)
            issues = feedback_json.get("issues", [])
            is_perfect = feedback_json.get("is_perfect", False)

            if not issues:
                is_perfect = True

            state.latest_feedback = {"issues": issues}

            if is_perfect:
                system_logger.info("[VLM Critic] Evaluation complete. Layout deemed perfect with 0 structural issues.")
            else:
                system_logger.info(f"[VLM Critic] Evaluation complete. Identified {len(issues)} academic emphasis issue(s) requiring layout adjustment.")

            return is_perfect
        
        except Exception as e:
            system_logger.error(f"CriticAgent evaluation failed: {str(e)}")
            return False