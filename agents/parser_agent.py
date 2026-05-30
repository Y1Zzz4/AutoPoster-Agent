import os
from typing import List
from markdown_it import MarkdownIt
from core.state_context import ContentBlock
from utils.logger import system_logger
import base64
import mimetypes

class ParserAgent:
    """
    ParserAgent is responsible for reading source documents (Markdown format),
    parsing their Abstract Syntax Tree (AST), and chunking them into structured ContentBlocks.
    """
    
    def __init__(self):
        # Initialize the markdown-it parser
        # markdown-it is chosen for its strict CommonMark compliance and detailed AST generation.
        self.md = MarkdownIt()
        system_logger.info("ParserAgent initialized successfully.")
    def _create_text_block(self, text: str) -> ContentBlock:
            """
            Helper method to encapsulate text into a ContentBlock and calculate its token weight.
            """
            cleaned_text = text.strip()
            
            # Mathematical approximation of token weight:
            # Assuming 1 LLM Token ~= 4 English characters or ~1.5 Chinese characters.
            # We use a base division of 3.0 to estimate the spatial weight this text will occupy.
            # The max(..., 10.0) ensures that even a very short title gets a minimum bounding box.
            estimated_weight = max(len(cleaned_text) / 3.0, 10.0)
            
            return ContentBlock(
                block_type="text",
                content=cleaned_text,
                token_weight=estimated_weight
            )
        
    def _encode_local_image(self, image_path: str, md_filepath: str) -> str:
        """
        Encode a local image file to a Base64 string for HTML rendering.
            
        Args:
            image_path (str): The raw path parsed from the markdown AST.
            md_filepath (str): The absolute path of the source markdown file.
                
        Returns:
            str: Base64 encoded Data URI scheme.
        """
        if os.path.isabs(image_path):
            target_path = image_path
        else:
            md_dir = os.path.dirname(os.path.abspath(md_filepath))
            target_path = os.path.normpath(os.path.join(md_dir, image_path))
                
        if not os.path.exists(target_path):
            system_logger.warning(f"Local image not found: {target_path}")
            return ""
                
        mime_type, _ = mimetypes.guess_type(target_path)
        mime_type = mime_type or 'image/png'
            
        with open(target_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
                
        return f"data:{mime_type};base64,{encoded_string}"
    
    def parse_markdown(self, filepath: str) -> List[ContentBlock]:
        """
        Main pipeline to parse a markdown file.
        """
        if not os.path.exists(filepath):
            system_logger.error(f"Input file missing: {filepath}")
            raise FileNotFoundError(f"Input file missing: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as file:
            raw_text = file.read()

        tokens = self.md.parse(raw_text)
        blocks: List[ContentBlock] = []
        current_text_buffer = ""
        
        for token in tokens:
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "image":
                        if current_text_buffer.strip():
                            blocks.append(self._create_text_block(current_text_buffer))
                            current_text_buffer = "" 
                            
                        raw_image_src = child.attrGet("src")
                        
                        # 调用内部实例方法，此时 self 自动作为第一个参数隐式传递
                        base64_src = self._encode_local_image(raw_image_src, filepath)
                        
                        if base64_src:
                            blocks.append(ContentBlock(
                                block_type="image",
                                content=base64_src,
                                token_weight=150.0 
                            ))
                            system_logger.info(f"Image extracted and encoded: {raw_image_src}")
                            
                    elif child.type in ["text", "code_inline"]:
                        current_text_buffer += child.content

            elif token.type in ["text", "code_inline"]:
                current_text_buffer += token.content
                
            elif token.type in ["paragraph_close", "heading_close"]:
                current_text_buffer += "\n\n"

        if current_text_buffer.strip():
            blocks.append(self._create_text_block(current_text_buffer))

        return blocks

    