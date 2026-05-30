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
        Processes text blocks sequentially and updates their content in-place.
        Leaves image blocks untouched.
        """
        system_logger.info("SummarizerAgent started processing long text blocks.")
        
        for block in state.content_blocks:
            if block.block_type == "text" and len(block.content) > 300:
                # Construct strict prompt for summarization
                sys_prompt = (
                    "You are an academic editor preparing text for a research poster. "
                    "Your objective is to condense the provided text to a maximum of 80 words. "
                    "Retain all key mathematical formulas, metric percentages, and core methodologies. "
                    "Use bullet points if it improves readability. Output ONLY the summarized text."
                )
                
                try:
                    response = await self.llm.chat.completions.create(
                        model=self.model_name,
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": block.content}
                        ],
                        temperature=0.2 
                    )
                    
                    summarized_text = response.choices[0].message.content.strip()
                    
                    # Update block state and recalculate its spatial weight
                    block.content = summarized_text
                    block.token_weight = max(len(summarized_text) / 3.0, 10.0)
                    
                except Exception as e:
                    system_logger.error(f"Failed to summarize block {block.block_id}: {str(e)}")
                    
        system_logger.info("SummarizerAgent execution completed.")