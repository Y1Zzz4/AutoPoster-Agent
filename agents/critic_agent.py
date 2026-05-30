import json
import base64
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class CriticAgent:
    """
    Semantic Editor Critic:
    Evaluates multi-modal alignment, data-ink ratio, and narrative pacing.
    Assumes physical boundaries are mathematically guaranteed by the Cartesian engine.
    """
    def __init__(self):
        self.vision_client = api_client.critic_client
        self.model_name = "qwen-vl-max"

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"

    def _extract_core_claims(self, state: SystemState) -> str:
        """
        Extracts the foundational scientific claims from the Abstract or Introduction
        to serve as the semantic baseline for VLM evaluation.
        """
        for card in state.cards:
            title_lower = card.title.lower()
            if "abstract" in title_lower or "introduction" in title_lower:
                # Use LOD 0 to provide the VLM with the maximum uncompressed context
                return card.text_lods.get(0, "")[:1000]
        return "No explicit Abstract found. Infer core contributions from visual layout."

    async def evaluate_layout(self, state: SystemState, image_path: str) -> bool:
        """
        Executes a high-dimensional Vision-Language Model review focusing on
        Scientific Communication Quality.
        """
        system_logger.info("[VLM Critic] Initiating multi-modal semantic inspection...")
        base64_image = self._encode_image(image_path)
        
        core_claims = self._extract_core_claims(state)
        expected_structure = [f"ID {c.card_id}: {c.title}" for c in state.cards]

        sys_prompt = (
            "You are an elite Scientific Chief Editor reviewing an academic poster. "
            "Physical layout constraints (overflow, text clipping) are mathematically guaranteed to be correct by the rendering engine. Do NOT evaluate them.\n\n"
            "Your objective is to evaluate the Scientific Communication Quality based on these high-dimensional criteria:\n"
            "1. Cross-Modal Alignment: Does the text accurately describe the adjacent charts/images? Report if critical text context is missing next to a figure.\n"
            "2. Data-Ink Ratio & Visual Salience: Are the core quantitative results visually dominant? If critical data is buried in dense text blocks, it is a flaw.\n"
            "3. Narrative Pacing: Is there visual fatigue? (e.g., A massive block of text without visual breaks).\n\n"
            "Output strictly valid JSON. Format:\n"
            "{\n"
            "  \"analysis\": \"Analyze semantic alignment and visual salience against the core claims.\",\n"
            "  \"issues\": [{\"card_id\": \"target_card_id\", \"description\": \"Actionable directive, e.g., 'Core result is not prominent, suggest CSS highlight' or 'Image lacks context.'\"}],\n"
            "  \"is_perfect\": boolean\n"
            "}"
        )

        user_prompt = (
            f"Core Claims of the Paper:\n{core_claims}\n\n"
            f"Expected Semantic Flow:\n{expected_structure}\n\n"
            "Examine the poster image. Verify that the core claims are visually salient and multi-modal elements are aligned."
        )

        try:
            response = await self.vision_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt}, 
                        {"type": "image_url", "image_url": {"url": base64_image}}
                    ]}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            feedback_json: Dict[str, Any] = json.loads(response.choices[0].message.content)
            issues = feedback_json.get("issues", [])
            is_perfect = feedback_json.get("is_perfect", False)

            if not issues:
                is_perfect = True

            # Stateless Overwrite (Markov Property)
            state.latest_feedback = {"issues": issues}

            if is_perfect:
                system_logger.info("[VLM Critic] Evaluation complete. Layout deemed perfect with 0 semantic issues.")
            else:
                system_logger.info(f"[VLM Critic] Evaluation complete. Identified {len(issues)} editorial issue(s).")

            return is_perfect

        except Exception as e:
            system_logger.error(f"[VLM Critic] Vision API failure: {str(e)}")
            return False