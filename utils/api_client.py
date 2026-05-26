import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from utils.logger import system_logger

# Load environment variables from the .env file into os.environ
load_dotenv()

class UnifiedLLMClient:
    """
    A unified asynchronous client to handle API requests for different LLM providers.
    Uses the OpenAI compatible format for both DeepSeek and Qwen.
    """
    
    def __init__(self):
        # Initialize DeepSeek Client (For Layout Planning & Parsing)
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL")
        
        if not deepseek_api_key:
            system_logger.error("DEEPSEEK_API_KEY is missing in the environment.")
            raise ValueError("DEEPSEEK_API_KEY is required.")
            
        self.planner_client = AsyncOpenAI(
            api_key=deepseek_api_key,
            base_url=deepseek_base_url
        )
        
        # Initialize Qwen Client (For Visual Critique)
        qwen_api_key = os.getenv("QWEN_API_KEY")
        qwen_base_url = os.getenv("QWEN_BASE_URL")
        
        if not qwen_api_key:
            system_logger.error("QWEN_API_KEY is missing in the environment.")
            raise ValueError("QWEN_API_KEY is required.")
            
        self.critic_client = AsyncOpenAI(
            api_key=qwen_api_key,
            base_url=qwen_base_url
        )
        
        system_logger.info("UnifiedLLMClient initialized successfully.")

# Instantiate a singleton client to be imported by all Agent modules
api_client = UnifiedLLMClient()