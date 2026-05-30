import json
from core.state_context import SystemState
from utils.api_client import api_client
from utils.logger import system_logger

class SummarizerAgent:
    """
    Compresses long document text blocks to fit poster spatial constraints 
    while preserving core academic concepts and metrics.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"

    async def execute_summary(self, state: SystemState) -> None:
        """
        Intelligently compresses long academic text. 
        Threshold increased to 800 characters to preserve context.
        """
        system_logger.info("SummarizerAgent evaluating text blocks for P2P conversion...")
        
        for block in state.content_blocks:
            # [UPDATE]: Threshold raised to 800 chars (~150 words). 
            # Only summarize truly overwhelming paragraphs.
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
                    
                    summarized_html = response.choices[0].message.content.strip()
                    
                    # Update content with HTML lists and adjust spatial weight
                    block.content = summarized_html
                    # Recalculate weight based on HTML tag density approximation
                    block.token_weight = max(len(summarized_html) / 4.0, 15.0)
                    system_logger.info(f"Summarized block {block.block_id} into bullet points.")
                    
                except Exception as e:
                    system_logger.error(f"Failed to summarize block {block.block_id}: {str(e)}")
                    
        system_logger.info("SummarizerAgent execution completed.")