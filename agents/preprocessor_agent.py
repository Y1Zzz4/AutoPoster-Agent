import os
from utils.api_client import api_client
from utils.logger import system_logger

class PreprocessorAgent:
    """
    Executes global semantic compression on the raw markdown input 
    before it enters the parsing pipeline.
    """
    def __init__(self):
        self.llm = api_client.planner_client
        self.model_name = "deepseek-v4-pro"
        self.target_word_count = 800

    async def compress_document(self, filepath: str) -> str:
        """
        Reads the markdown file, evaluates its length, and compresses it via LLM if it exceeds the threshold.
        Generates a new '_compressed' file to maintain data traceability.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_text = f.read()

        word_count = len(raw_text.split())
        if word_count <= self.target_word_count:
            system_logger.info(f"Document length ({word_count} words) is within limits. Skipping pre-compression.")
            return filepath

        system_logger.info(f"Document exceeds target length ({word_count} > {self.target_word_count}). Initiating global compression...")

        sys_prompt = (
            "You are an academic editor. Your task is to compress the provided Markdown paper "
            f"down to approximately {self.target_word_count} words.\n\n"
            "Rules:\n"
            "1. PRESERVE ALL Markdown headings (`#`, `##`, etc.) strictly without altering their hierarchy.\n"
            "2. PRESERVE ALL image syntaxes strictly (e.g., `![alt](path)`).\n"
            "3. PRESERVE ALL mathematical formulas, metrics, and key data points.\n"
            "4. Condense verbose paragraphs while strictly retaining the original scientific meaning and logical flow.\n"
            "5. Output ONLY the raw Markdown string. Do not use code block wrappers."
        )

        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": raw_text}
                ],
                temperature=0.1
            )

            compressed_text = response.choices[0].message.content.strip()
            
            if compressed_text.startswith("```markdown"):
                compressed_text = compressed_text[11:-3].strip()
            elif compressed_text.startswith("```"):
                compressed_text = compressed_text[3:-3].strip()

            base, ext = os.path.splitext(filepath)
            new_filepath = f"{base}_compressed{ext}"

            with open(new_filepath, 'w', encoding='utf-8') as f:
                f.write(compressed_text)

            system_logger.info(f"Global pre-compression complete. Saved to: {new_filepath}")
            return new_filepath

        except Exception as e:
            system_logger.error(f"Global pre-compression failed: {str(e)}. Proceeding with original document.")
            return filepath