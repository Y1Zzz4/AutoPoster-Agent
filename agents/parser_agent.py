import os
import base64
import mimetypes
import urllib.parse
from pathlib import Path
from typing import List
from markdown_it import MarkdownIt
from core.state_context import ContentBlock, PosterCard
from utils.logger import system_logger

class ParserAgent:
    """
    ParserAgent parses the AST of a Markdown document and chunks it into Semantic PosterCards.
    Assumes inputs are self-contained folders (MD file + relative image assets) or Web URLs.
    """
    
    def __init__(self):
        self.md = MarkdownIt()
        system_logger.info("ParserAgent initialized.")

    def _encode_local_image(self, image_path: str, md_filepath: str) -> str:
        """
        Encodes images by resolving relative paths strictly against the MD file's directory.
        
        Args:
            image_path (str): The raw path parsed from the markdown AST.
            md_filepath (str): The absolute path of the source markdown file.
            
        Returns:
            str: Base64 encoded Data URI scheme.
        """
        if image_path.startswith(('http://', 'https://', 'data:')):
            return image_path
            
        clean_path = urllib.parse.unquote(image_path)
        
        if clean_path.startswith('file:///'):
            clean_path = clean_path[8:]
        elif clean_path.startswith('file://'):
            clean_path = clean_path[7:]

        md_dir = Path(md_filepath).parent
        target_path = (md_dir / clean_path).resolve()
        
        if not target_path.exists():
            system_logger.warning(f"Image missing in document folder: {target_path}")
            return ""
            
        mime_type, _ = mimetypes.guess_type(str(target_path))
        mime_type = mime_type or 'image/png'
        
        with open(target_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
            
        return f"data:{mime_type};base64,{encoded_string}"

    def parse_markdown(self, filepath: str) -> List[PosterCard]:
        """
        Parses a markdown file into a series of semantic PosterCards based on structural headings.
        Calculates initial token_weight using a Natural Height Estimation algorithm.
        
        Args:
            filepath (str): Absolute path to the source markdown file.
            
        Returns:
            List[PosterCard]: A structured list of segmented academic sections.
        """
        if not os.path.exists(filepath):
            system_logger.error(f"Input file missing: {filepath}")
            raise FileNotFoundError(f"Input file missing: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as file:
            raw_text = file.read()

        tokens = self.md.parse(raw_text)
        
        cards: List[PosterCard] = []
        current_card = PosterCard(title="") 
        current_text_buffer = ""
        is_inside_heading = False 
        
        for token in tokens:
            # --- 1. Encountering a Heading Open Token ---
            if token.type == "heading_open":
                is_inside_heading = True
                
                # Flush existing text buffer into the previous card before sealing it
                if current_text_buffer.strip():
                    current_card.blocks.append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
                    current_text_buffer = ""
                
                # If the card has a valid title string or content, archive it.
                if current_card.title.strip() or current_card.blocks:
                    text_len = sum(len(b.content) for b in current_card.blocks if b.block_type == 'text')
                    img_count = sum(1 for b in current_card.blocks if b.block_type == 'image')
                    
                    # [UPDATE]: Natural Height Estimation
                    # Base padding=100px, 1 char ~ 0.8px height, 1 image ~ 350px height
                    current_card.token_weight = 100.0 + (text_len * 0.8) + (img_count * 350.0)
                    
                    cards.append(current_card)
                
                # Instantiate a clean card to capture the upcoming heading title
                current_card = PosterCard(title="") 

            # --- 2. Extracting Heading Inner Text ---
            elif token.type == "inline" and is_inside_heading:
                current_card.title = token.content

            # --- 3. Heading Close Token ---
            elif token.type == "heading_close":
                is_inside_heading = False
                if not current_card.title.strip():
                    current_card.title = "Section"

            # --- 4. Processing Body Text and Media Blocks ---
            elif token.type == "inline" and not is_inside_heading and token.children:
                for child in token.children:
                    if child.type == "image":
                        if current_text_buffer.strip():
                            current_card.blocks.append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
                            current_text_buffer = "" 
                            
                        raw_image_src = child.attrGet("src")
                        base64_src = self._encode_local_image(raw_image_src, filepath)
                        if base64_src:
                            current_card.blocks.append(ContentBlock(block_type="image", content=base64_src))
                            
                    elif child.type in ["text", "code_inline"]:
                        current_text_buffer += child.content

            elif token.type in ["paragraph_close"]:
                current_text_buffer += "\n\n"

        # --- Final Card Settlement (EOF) ---
        if current_text_buffer.strip():
            current_card.blocks.append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
            
        if current_card.title.strip() or current_card.blocks:
            text_len = sum(len(b.content) for b in current_card.blocks if b.block_type == 'text')
            img_count = sum(1 for b in current_card.blocks if b.block_type == 'image')
            
            # [UPDATE]: Natural Height Estimation for the last card
            current_card.token_weight = 100.0 + (text_len * 0.8) + (img_count * 350.0)
            
            cards.append(current_card)

        return cards