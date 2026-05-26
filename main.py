import asyncio
import os
import sys
from utils.logger import system_logger
from core.pipeline import AutoPosterPipeline

async def main():
    """
    Main entry point for the AutoPoster-Agent system.
    """
    system_logger.info("Starting AutoPoster-Agent System...")
    
    # Define the input file path (resolving absolute path for safety)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "assets", "inputs", "sample_paper.md")
    
    if not os.path.exists(input_file):
        system_logger.error(f"Cannot find input file at: {input_file}")
        sys.exit(1)
        
    try:
        # Instantiate the pipeline orchestrator
        pipeline = AutoPosterPipeline()
        
        # Run the multi-agent generation loop
        final_output_path = await pipeline.run(input_file)
        
        system_logger.info("="*50)
        system_logger.info(f"SUCCESS! Poster generated at:\n{final_output_path}")
        system_logger.info("="*50)
        
    except Exception as e:
        system_logger.error(f"Pipeline crashed with an unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Windows specific fix for asyncio and Playwright
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    # Execute the asynchronous main function
    asyncio.run(main())