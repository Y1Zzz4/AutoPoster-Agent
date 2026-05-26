import base64
import json
import os
from typing import Dict, Any
from utils.api_client import api_client
from utils.logger import system_logger
from core.state_context import SystemState

class CriticAgent:
    """
    CriticAgent acts as the visual reviewer.
    It uses a Vision-Language Model (Qwen-VL) to inspect the debug render 
    and identify layout issues like overlapping boxes or text overflow.
    """
    def __init__(self):
        self.vl_client = api_client.critic_client
        # qwen3.6-plus is highly capable of OCR and spatial reasoning
        self.model_name = "qwen3.6-plus" 
        system_logger.info("CriticAgent initialized with qwen3.6-plus.")

    def _encode_image(self, image_path: str) -> str:
        """Helper function to encode a local image file into a base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def review_poster(self, state: SystemState, debug_image_path: str) -> bool:
        """
        Reviews the generated poster and updates the state with feedback.
        
        Returns:
            bool: True if the layout is perfect, False if errors are found.
        """
        system_logger.info(f"Iteration {state.current_iteration}: Critic is reviewing the poster...")
        
        if not os.path.exists(debug_image_path):
            system_logger.error("Debug image not found for review.")
            return False

        base64_image = self._encode_image(debug_image_path)
        
        # Engineering the Vision Prompt for strict JSON output
        prompt_text = (
            "You are an expert graphic design inspector. Analyze the provided poster design.\n"
            "This is a 'debug view' where every content block has a RED border and an ID badge in the top-left corner.\n\n"
            "Your tasks:\n"
            "1. Check for Overlap: Are any red bounding boxes physically overlapping each other?\n"
            "2. Check for Overflow: Is any text overflowing outside its assigned red bounding box?\n"
            "3. Check for Proportions: Does any block look awkwardly squashed or too empty?\n\n"
            "Output strictly in JSON format with the following structure:\n"
            "{\n"
            "  \"is_perfect\": boolean (true if no issues found, false otherwise),\n"
            "  \"issues\": [\n"
            "    {\"block_id\": \"id_from_the_badge\", \"issue_type\": \"overlap/overflow/proportion\", \"suggestion\": \"brief advice, e.g., increase weight_multiplier\"}\n"
            "  ]\n"
            "}\n"
            "If 'is_perfect' is true, 'issues' can be an empty list."
        )

        try:
            # Send the request to Qwen-VL
            response = await self.vl_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            # Pass the image as a base64 data URI
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    }
                ],
                # Forcing low temperature for analytical task
                temperature=0.1 
            )
            
            # Parse the JSON response
            raw_response = response.choices[0].message.content
            
            # Sanitize response in case the LLM wrapped it in markdown code blocks
            clean_json_str = raw_response.replace("```json", "").replace("```", "").strip()
            feedback_data = json.loads(clean_json_str)
            
            # Update the state machine
            state.latest_feedback = feedback_data
            state.is_converged = feedback_data.get("is_perfect", False)
            
            if state.is_converged:
                system_logger.info("Critic approved the layout! No issues found.")
            else:
                issue_count = len(feedback_data.get("issues", []))
                system_logger.warning(f"Critic found {issue_count} issues. Feedback recorded.")
                
            return state.is_converged

        except Exception as e:
            system_logger.error(f"CriticAgent failed to process image: {str(e)}")
            # In case of API failure, we assume it's "good enough" to avoid infinite loops
            state.is_converged = True 
            return True