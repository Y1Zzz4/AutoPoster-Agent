import json
from typing import Dict, Any
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class PlannerAgent:
    """
    PlannerAgent is the "Brain" of the spatial layout.
    It uses an LLM (DeepSeek) to determine the semantic grouping (order) 
    and relative spatial importance (weight multiplier) of each ContentBlock.
    """

    def __init__(self):
        # We reuse the global async client instantiated in api_client.py
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro" # Standard identifier for DeepSeek API
        system_logger.info("PlannerAgent initialized.")

    async def plan_layout(self, state: SystemState) -> None:
        """
        Calls the LLM to generate a layout strategy, and updates the state's content_blocks.
        This is an asynchronous function to prevent blocking the main thread.
        """
        system_logger.info(f"Iteration {state.current_iteration}: Requesting layout plan from LLM.")

        # 1. Prepare the input data payload for the LLM
        blocks_data = [
            {
                "block_id": b.block_id,
                "type": b.block_type,
                "current_weight": b.token_weight,
                # Truncate content to save tokens, the LLM only needs to understand the semantic meaning, not the full text
                "content_preview": b.content[:100] + "..." if len(b.content) > 100 else b.content
            }
            for b in state.content_blocks
        ]

        # 2. Construct the intelligent prompt
        system_prompt = (
            "You are an expert graphic design AI orchestrating a Poster layout. "
            "You will be given a list of ContentBlocks. Your task is to output a JSON object "
            "that defines the 'reading order' and 'spatial importance' of these blocks.\n\n"
            "Rules:\n"
            "1. Output a strictly valid JSON object with a key 'layout_plan' containing a list of objects.\n"
            "2. Each object must have 'block_id', 'reasoning' (why you placed it here), "
            "and 'weight_multiplier' (float, default 1.0. Increase if the block needs more physical space on the poster).\n"
            "3. The order of the list determines how the BSP algorithm will group them visually (items adjacent in the list will be grouped together)."
        )

        user_prompt = f"Here are the document blocks:\n{json.dumps(blocks_data, indent=2)}\n"

        # 3. Inject Critic's Feedback (The closed-loop magic!)
        if state.current_iteration > 0 and state.latest_feedback:
            user_prompt += (
                f"\nCRITICAL FEEDBACK from previous iteration:\n"
                f"{json.dumps(state.latest_feedback, indent=2)}\n"
                "Please adjust the 'weight_multiplier' or the ordering to fix these visual errors (e.g., if text overflowed, increase its multiplier)."
            )

        try:
            # 4. Call the LLM (Asynchronously)
            # We enforce JSON output mode to guarantee structured data parsing
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3 # Low temperature for more deterministic and logical layouts
            )

            response_content = response.choices[0].message.content
            plan_json = json.loads(response_content)
            
            # 5. Apply the LLM's strategy to our State Machine
            self._apply_plan_to_state(plan_json, state)
            system_logger.info("Layout plan successfully applied to state.")

        except Exception as e:
            system_logger.error(f"Failed to generate or parse LLM layout plan: {str(e)}")
            # Fallback: If LLM fails, we just keep the original parser order and weights, 
            # ensuring the system does not crash and can still pass to the BSP algorithm.

    def _apply_plan_to_state(self, plan_json: Dict[str, Any], state: SystemState) -> None:
        """
        Mutates the SystemState based on the JSON plan returned by the LLM.
        """
        layout_list = plan_json.get("layout_plan", [])
        
        # Create a lookup dictionary for fast access
        block_map = {b.block_id: b for b in state.content_blocks}
        reordered_blocks = []

        for item in layout_list:
            b_id = item.get("block_id")
            multiplier = float(item.get("weight_multiplier", 1.0))
            
            if b_id in block_map:
                block = block_map[b_id]
                # Apply the multiplier to the base weight
                block.token_weight = block.token_weight * multiplier
                reordered_blocks.append(block)
                # Remove from map to track missing blocks
                del block_map[b_id]
                
        # Safety net: Append any blocks the LLM hallucinated away
        for remaining_block in block_map.values():
            reordered_blocks.append(remaining_block)
            
        # Update the global state with the new semantically ordered and weighted list
        state.content_blocks = reordered_blocks