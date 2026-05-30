import math
import re
import asyncio
from core.state_context import SystemState, ContentBlock, PosterCard
from utils.api_client import api_client
from utils.logger import system_logger

class SummarizerAgent:
    """
    Pre-computes and bakes a 4-tier Semantic Level of Detail (LOD) matrix 
    concurrently to eliminate runtime LLM bottlenecks.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"

    async def execute_summary(self, state: SystemState) -> None:
        system_logger.info("SummarizerAgent baking 4-tier Semantic LODs (100%, 75%, 50%, 25%) concurrently...")
        
        tasks = []
        for card in state.cards:
            text_blocks = [b for b in card.blocks if b.block_type == "text"]
            if not text_blocks:
                continue
                
            base_text = "\n\n".join(b.content for b in text_blocks)
            card.text_lods[0] = base_text
            card.current_lod = 0

            # Pre-bake compressed tiers only for content-heavy cards
            if len(base_text) > 250:
                tasks.append(self._generate_all_lods(card, base_text))
            else:
                card.text_lods[1] = base_text
                card.text_lods[2] = base_text
                card.text_lods[3] = base_text
                
        if tasks:
            await asyncio.gather(*tasks)
            
        # Synchronize Initial Mathematical Weights
        for card in state.cards:
            self._apply_lod_to_blocks(card)
            
        system_logger.info("4-tier Semantic LOD pre-computation complete.")

    async def _generate_all_lods(self, card: PosterCard, base_text: str):
        p1 = "Compress this academic text. Retain almost all details, core metrics, and formulas, but remove verbose transitions. Format as HTML (`<p>` or `<ul><li>`). Reduce total length to exactly 70-80%."
        p2 = "Compress this academic text into 3-4 highly readable HTML bullet points (`<ul><li>`). Keep core metrics. Reduce length to exactly 40-50%."
        p3 = "Extremely compress this text into 2 concise HTML bullet points (`<ul><li>`). ONLY keep the absolute final results and formulas. Reduce length to exactly 20-25%."
        
        async def fetch_tier(prompt: str) -> str:
            try:
                resp = await self.llm.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": base_text}],
                    temperature=0.1
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                system_logger.error(f"LOD generation tier failed: {e}")
                return base_text

        l1, l2, l3 = await asyncio.gather(fetch_tier(p1), fetch_tier(p2), fetch_tier(p3))
        card.text_lods[1] = l1
        card.text_lods[2] = l2
        card.text_lods[3] = l3

    def _apply_lod_to_blocks(self, card: PosterCard) -> None:
        """
        Updates text content and resynchronizes rigid-flex layout metrics.
        """
        card.blocks = [b for b in card.blocks if b.block_type != "text"]
        current_text = card.text_lods.get(card.current_lod, "")
        
        if current_text:
            card.blocks.insert(0, ContentBlock(block_type="text", content=current_text))
            
        text_len = len(current_text)
        img_count = sum(1 for b in card.blocks if b.block_type == 'image')
        title_lines = math.ceil(len(card.title) / 25.0)
        list_items = current_text.count('<li>')
        
        # Rigidity mathematical estimation formula
        rigid_h = 80.0 + (title_lines * 40.0) + (math.ceil(text_len / 45.0) * 32.0) + (list_items * 15.0)
        card.token_weight = rigid_h + (img_count * 380.0)