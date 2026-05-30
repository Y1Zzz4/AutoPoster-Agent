import os
from typing import List
from markdown_it import MarkdownIt
from core.state_context import ContentBlock,PosterCard
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
    
    def parse_markdown(self, filepath: str) -> List[PosterCard]:
        """
        Main pipeline to parse a markdown file.
        """
        if not os.path.exists(filepath):
            system_logger.error(f"Input file missing: {filepath}")
            raise FileNotFoundError(f"Input file missing: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as file:
            raw_text = file.read()

        tokens = self.md.parse(raw_text)
        
        cards: List[PosterCard] = []
        current_card = PosterCard(title="Header") # 默认创建 Header 卡片
        current_text_buffer = ""
        
        for token in tokens:
            # 1. 遇到新的 Heading，立刻结算旧卡片，创建新卡片
            if token.type == "heading_open":
                if current_text_buffer.strip():
                    current_card.blocks.append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
                    current_text_buffer = ""
                
                # 如果当前卡片非空，装入列表
                if current_card.blocks or current_card.title == "Header":
                    # 粗略估算卡片权重 (文字越长、图片越多，权重越大)
                    text_len = sum(len(b.content) for b in current_card.blocks if b.block_type == 'text')
                    img_count = sum(1 for b in current_card.blocks if b.block_type == 'image')
                    current_card.token_weight = max(text_len / 3.0, 10.0) + (img_count * 100.0)
                    cards.append(current_card)
                
                # 开启新卡片
                current_card = PosterCard(title="New Section") # 标题将在后续 text 节点中被覆盖

            # 2. 捕获标题内容
            elif token.type == "text" and tokens[tokens.index(token)-1].type == "heading_open":
                current_card.title = token.content

            # 3. 处理图片与文字
            elif token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "image":
                        # 遇到图片前，先清空并存入当前积累的文字
                        if current_text_buffer.strip():
                            current_card.blocks.append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
                            current_text_buffer = "" 
                            
                        raw_image_src = child.attrGet("src")
                        base64_src = self._encode_local_image(raw_image_src, filepath)
                        if base64_src:
                            # [核心突破]：图片直接作为 Block 塞入当前正在处理的语义卡片中！
                            current_card.blocks.append(ContentBlock(block_type="image", content=base64_src))
                            
                    elif child.type in ["text", "code_inline"]:
                        # 排除标题文本，防止重复
                        if not (tokens[tokens.index(token)-1].type == "heading_open"):
                            current_text_buffer += child.content

            elif token.type in ["paragraph_close"]:
                current_text_buffer += "\n\n"

        # 结算最后一张卡片
        if current_text_buffer.strip():
            current_card.blocks.append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
        if current_card.blocks:
            text_len = sum(len(b.content) for b in current_card.blocks if b.block_type == 'text')
            img_count = sum(1 for b in current_card.blocks if b.block_type == 'image')
            current_card.token_weight = max(text_len / 3.0, 10.0) + (img_count * 100.0)
            cards.append(current_card)

        return cards

    