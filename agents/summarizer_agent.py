import json
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class SummarizerAgent:
    """
    Compresses long academic text blocks within Semantic Cards.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"

    async def execute_summary(self, state: SystemState) -> None:
        """
        Iterates through cards and their respective blocks. 
        Summarizes overly long text blocks into HTML lists.
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
            
            # Recalculate the entire card's token_weight if any text was compressed
            if has_modified:
                text_len = sum(len(b.content) for b in card.blocks if b.block_type == 'text')
                img_count = sum(1 for b in card.blocks if b.block_type == 'image')
                card.token_weight = max(text_len / 3.0, 10.0) + (img_count * 100.0)

        system_logger.info("SummarizerAgent execution completed.")