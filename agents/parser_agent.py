import os
from typing import List
from markdown_it import MarkdownIt
from core.state_context import ContentBlock
from utils.logger import system_logger

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

    def parse_markdown(self, filepath: str) -> List[ContentBlock]:
        """
        Main pipeline to parse a markdown file.
        
        Args:
            filepath (str): The local path to the .md file.
            
        Returns:
            List[ContentBlock]: A list of structured data blocks ready for layout planning.
        """
        if not os.path.exists(filepath):
            system_logger.error(f"Failed to locate input file: {filepath}")
            raise FileNotFoundError(f"Input file missing: {filepath}")

        # Read the raw text from the document
        with open(filepath, 'r', encoding='utf-8') as file:
            raw_text = file.read()

        system_logger.info(f"Parsing AST for file: {filepath}")
        
        # Convert raw markdown string into a list of Token objects (AST)
        tokens = self.md.parse(raw_text)
        
        blocks: List[ContentBlock] = []
        current_text_buffer = ""
        
        for token in tokens:
            # 1. Image Extraction Logic
            # Images in Markdown are typically nested inside 'inline' tokens.
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "image":
                        # Flush any pending text into a block before adding the image
                        if current_text_buffer.strip():
                            blocks.append(self._create_text_block(current_text_buffer))
                            current_text_buffer = "" 
                            
                        image_src = child.attrGet("src")
                        # We assign a fixed initial token_weight for images.
                        # This weight can be dynamically adjusted later based on image aspect ratio.
                        blocks.append(ContentBlock(
                            block_type="image",
                            content=image_src,
                            token_weight=150.0 
                        ))
                        system_logger.info(f"Image extracted: {image_src}")

                    elif child.type in ["text", "code_inline"]:
                        current_text_buffer += child.content

            # 2. Text Extraction Logic (Headings and Paragraphs)
            elif token.type in ["inline", "text"] and token.content:
                # Append the content to our buffer
                current_text_buffer += token.content + "\n"
                
            # When a paragraph or heading closes, we add a newline for formatting
            elif token.type in ["paragraph_close", "heading_close"]:
                current_text_buffer += "\n"

        # Flush the final buffer if there is any remaining text
        if current_text_buffer.strip():
            blocks.append(self._create_text_block(current_text_buffer))

        system_logger.info(f"ParserAgent finished. Extracted {len(blocks)} blocks.")
        return blocks

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