import os
from typing import List
from markdown_it import MarkdownIt
from core.state_context import ContentBlock
from utils.logger import system_logger
from pathlib import Path
import base64
import mimetypes
import urllib.parse

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
        Robust local image encoder. Resolves complex absolute/relative paths and URI encodings.
        """
        # 1. Pass through web links and existing base64 strings
        if image_path.startswith(('http://', 'https://', 'data:')):
            return image_path
            
        # 2. Decode URI components (e.g., "%20" to " ")
        clean_path = urllib.parse.unquote(image_path)
        
        # Strip 'file://' protocol if present to prevent Pathlib parsing errors
        if clean_path.startswith('file:///'):
            clean_path = clean_path[8:] # Strip 'file:///'
        elif clean_path.startswith('file://'):
            clean_path = clean_path[7:]

        # 3. Use robust pathlib to determine path type
        p = Path(clean_path)
        if p.is_absolute():
            target_path = p
        else:
            # If relative, anchor it to the markdown file's directory
            md_dir = Path(md_filepath).parent
            target_path = md_dir / p
            
        # Resolve to clean absolute path, removing any '../'
        target_path = target_path.resolve()
        
        if not target_path.exists():
            system_logger.warning(f"Local image not found at resolved path: {target_path}")
            return ""
            
        mime_type, _ = mimetypes.guess_type(str(target_path))
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
                        base64_src = self._encode_local_image(raw_image_src, filepath)
                        
                        if base64_src:
                            blocks.append(ContentBlock(
                                block_type="image",
                                content=base64_src,
                                token_weight=150.0 
                            ))
                            
                    elif child.type in ["text", "code_inline"]:
                        current_text_buffer += child.content

            elif token.type == "heading_open":
                if token.tag == "h1":
                    current_text_buffer += "<h1 class='main-poster-title'>"
                else:
                    current_text_buffer += f"<{token.tag} class='section-title'>"

            elif token.type == "heading_close":
                current_text_buffer += f"</{token.tag}>\n"

            elif token.type == "paragraph_open":
                current_text_buffer += "<p class='content-text'>"

            elif token.type == "paragraph_close":
                current_text_buffer += "</p>\n"

            elif token.type in ["text", "code_inline"]:
                current_text_buffer += token.content

        if current_text_buffer.strip():
            blocks.append(self._create_text_block(current_text_buffer))

        return blocks

    