import math
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class SummarizerAgent:
    """
    Handles both initial long-text compression and dynamic overflow compression.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"

    async def execute_summary(self, state: SystemState) -> None:
        """
        Initial pass: Compresses excessively long academic text blocks into bullet points.
        """
        system_logger.info("SummarizerAgent evaluating text blocks for P2P conversion...")
        
        for card in state.cards:
            has_modified = False
            for block in card.blocks:
                if block.block_type == "text" and len(block.content) > 800:
                    sys_prompt = (
                        "You are an academic editor creating a Paper-to-Poster (P2P) layout. "
                        "Your objective is to condense the provided text into 3-4 highly readable bullet points. "
                        "Rules: \n"
                        "1. Preserve ALL mathematical metrics, percentages, and core methodologies.\n"
                        "2. Total length must not exceed 100 words.\n"
                        "3. Format the output STRICTLY as raw HTML using <ul> and <li> tags.\n"
                        "Do NOT wrap the output in markdown code blocks."
                    )
                    
                    try:
                        response = await self.llm.chat.completions.create(
                            model=self.model_name,
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": block.content}
                            ],
                            temperature=0.1 
                        )
                        
                        block.content = response.choices[0].message.content.strip()
                        has_modified = True
                        system_logger.info(f"Summarized block inside card '{card.title}' into bullet points.")
                        
                    except Exception as e:
                        system_logger.error(f"Failed to summarize block in card {card.card_id}: {str(e)}")
            
            if has_modified:
                self._recalculate_card_weight(card)

        system_logger.info("SummarizerAgent execution completed.")

    async def compress_overflow_card(self, state: SystemState) -> list:
        """
        Dynamic pass: Triggered by CriticAgent when a card physically overflows its boundaries.
        Returns a list of card IDs that were successfully compressed.
        """
        if not state.latest_feedback or "issues" not in state.latest_feedback:
            return []

        overflow_card_ids = set()
        for issue in state.latest_feedback["issues"]:
            desc = issue.get("description", "").lower()
            if "overflow" in desc or "cut off" in desc or "clip" in desc:
                c_id = issue.get("card_id")
                if c_id and c_id != "unknown":
                    overflow_card_ids.add(c_id)

        if not overflow_card_ids:
            return []

        compressed_ids = []
        for card in state.cards:
            if card.card_id in overflow_card_ids:
                text_blocks = [b for b in card.blocks if b.block_type == "text"]
                if not text_blocks:
                    continue

                # Target the longest text block to maximize space recovery
                target_block = max(text_blocks, key=lambda b: len(b.content))

                sys_prompt = (
                    "You are an academic editor. The current text overflows its physical poster container. "
                    "Compress the provided text to reduce its total character length by at least 30%. "
                    "Retain core metrics and mathematical formulas. "
                    "Output ONLY the compressed text in HTML format (use <ul>/<li> or <p>)."
                )

                try:
                    response = await self.llm.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": target_block.content}
                        ],
                        temperature=0.1
                    )
                    target_block.content = response.choices[0].message.content.strip()
                    compressed_ids.append(card.card_id)
                    system_logger.info(f"Dynamically compressed overflowed text for card: {card.card_id}")
                except Exception as e:
                    system_logger.error(f"Dynamic compression failed for card {card.card_id}: {str(e)}")
                    
        return compressed_ids

    def _recalculate_card_weight(self, card) -> None:
        """
        Mathematically synchronizes the token_weight with the Constrained Layout engine's 
        Bottom-Up Rigid Modeling formula to prevent layout coordinate oscillations.
        """
        text_len = sum(len(b.content) for b in card.blocks if b.block_type == 'text')
        img_count = sum(1 for b in card.blocks if b.block_type == 'image')
        title_lines = math.ceil(len(card.title) / 25.0)
        
        est_text_h = math.ceil(text_len / 45.0) * 32.0
        est_title_h = title_lines * 40.0
        est_img_h = img_count * 380.0
        
        # 80.0 represents the strict padding_base defined in the layout engine
        card.token_weight = 80.0 + est_title_h + est_text_h + est_img_h