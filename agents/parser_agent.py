import os
import json
import base64
import mimetypes
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any
from markdown_it import MarkdownIt
from core.state_context import ContentBlock, PosterCard
from utils.api_client import api_client
from utils.logger import system_logger

class ParserAgent:
    """
    Neuro-Symbolic Parser: 
    1. Symbolic: Extracts raw AST nodes accurately (text, images).
    2. Neural: Uses an LLM to logically group raw sections into cohesive PosterCards.
    """
    
    def __init__(self):
        self.md = MarkdownIt()
        # Reusing planner client for logical structural grouping
        self.llm = api_client.planner_client 
        self.model_name = "deepseek-v4-pro"
        system_logger.info("Neuro-Symbolic ParserAgent initialized.")

    def _encode_local_image(self, image_path: str, md_filepath: str) -> str:
        # (Image encoding logic remains strictly physical and symbolic)
        if image_path.startswith(('http://', 'https://', 'data:')):
            return image_path
            
        clean_path = urllib.parse.unquote(image_path)
        if clean_path.startswith('file:///'): clean_path = clean_path[8:]
        elif clean_path.startswith('file://'): clean_path = clean_path[7:]

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

    async def parse_markdown(self, filepath: str) -> List[PosterCard]:
        """
        Executes the neuro-symbolic parsing pipeline.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Input file missing: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as file:
            raw_text = file.read()

        # --- Phase 1: Symbolic Extraction ---
        tokens = self.md.parse(raw_text)
        raw_sections = []
        current_section = {"title": "Introduction", "blocks": []}
        current_text_buffer = ""
        is_inside_heading = False

        for token in tokens:
            if token.type == "heading_open":
                is_inside_heading = True
                if current_text_buffer.strip():
                    current_section["blocks"].append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
                    current_text_buffer = ""
                
                # Save the completed section and start a new one
                if current_section["blocks"] or current_section["title"] != "Introduction":
                    raw_sections.append(current_section)
                current_section = {"title": "", "blocks": []}

            elif token.type == "inline" and is_inside_heading:
                current_section["title"] = token.content

            elif token.type == "heading_close":
                is_inside_heading = False

            elif token.type == "inline" and not is_inside_heading and token.children:
                for child in token.children:
                    if child.type == "image":
                        if current_text_buffer.strip():
                            current_section["blocks"].append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
                            current_text_buffer = "" 
                        
                        raw_image_src = child.attrGet("src")
                        base64_src = self._encode_local_image(raw_image_src, filepath)
                        if base64_src:
                            current_section["blocks"].append(ContentBlock(block_type="image", content=base64_src))
                    elif child.type in ["text", "code_inline"]:
                        current_text_buffer += child.content

            elif token.type in ["paragraph_close"]:
                current_text_buffer += "\n\n"

        if current_text_buffer.strip():
            current_section["blocks"].append(ContentBlock(block_type="text", content=current_text_buffer.strip()))
        if current_section["blocks"] or current_section["title"]:
            raw_sections.append(current_section)

        # Separate the main paper title (always the first section)
        header_section = raw_sections[0]
        body_sections = raw_sections[1:]
        
        if not body_sections:
             return [self._build_card(header_section)]

        # --- Phase 2: Neural Semantic Grouping ---
        outline = [
            {
                "section_id": idx, 
                "title": sec["title"], 
                "text_length": sum(len(b.content) for b in sec["blocks"] if b.block_type == 'text'),
                "image_count": sum(1 for b in sec["blocks"] if b.block_type == 'image')
            }
            for idx, sec in enumerate(body_sections)
        ]
        
        system_logger.info("Requesting LLM to group document sections semantically...")
        grouped_plan = await self._request_semantic_grouping(outline)
        
        # --- Phase 3: Neuro-Symbolic Reassembly ---
        final_cards: List[PosterCard] = [self._build_card(header_section)]
        
        for group in grouped_plan:
            merged_title = group.get("merged_title", "Section")
            target_ids = group.get("section_ids", [])
            
            merged_card = PosterCard(title=merged_title)
            for sid in target_ids:
                if 0 <= sid < len(body_sections):
                    # Preserve original symbolic blocks precisely
                    merged_card.blocks.extend(body_sections[sid]["blocks"])
            
            if merged_card.blocks:
                self._calculate_natural_weight(merged_card)
                final_cards.append(merged_card)

        return final_cards

    async def _request_semantic_grouping(self, outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Commands the LLM to cluster raw sections into 3-5 major poster regions.
        """
        sys_prompt = (
            "You are an expert academic editor. Your task is to merge fragmented markdown "
            "sections into 3 to 5 cohesive semantic blocks for an academic poster.\n"
            "Rules:\n"
            "1. Group sequential sections logically (e.g., merge 'Datasets' and 'Training' into 'Methodology').\n"
            "2. Preserve the sequential order. Do NOT skip any section_id.\n"
            "3. Return ONLY a valid JSON array of objects. Each object must have:\n"
            "   - 'merged_title': A high-level academic title for the new block.\n"
            "   - 'section_ids': An array of integers representing the IDs to merge.\n"
            "Example format: [{\"merged_title\": \"Methodology\", \"section_ids\": [1, 2, 3]}]"
        )
        
        user_prompt = f"Document Outline:\n{json.dumps(outline, indent=2)}"
        
        try:
            response = await self.llm.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}, # Fallback: DeepSeek handles array in JSON wrapper or raw array
                temperature=0.1
            )
            content = response.choices[0].message.content.strip()
            
            # DeepSeek JSON format safeguard handling
            if content.startswith('```json'):
                content = content[7:-3].strip()
            
            parsed_json = json.loads(content)
            
            # Extract array if model wrapped it in an object like {"groups": [...]}
            if isinstance(parsed_json, dict):
                for key, val in parsed_json.items():
                    if isinstance(val, list):
                        return val
                return []
            return parsed_json
            
        except Exception as e:
            system_logger.error(f"Semantic grouping failed: {e}. Falling back to 1-to-1 mapping.")
            # Fallback: 1-to-1 mapping
            return [{"merged_title": item["title"], "section_ids": [item["section_id"]]} for item in outline]

    def _build_card(self, section_data: Dict[str, Any]) -> PosterCard:
        card = PosterCard(title=section_data["title"])
        card.blocks = section_data["blocks"]
        self._calculate_natural_weight(card)
        return card

    def _calculate_natural_weight(self, card: PosterCard) -> None:
        text_len = sum(len(b.content) for b in card.blocks if b.block_type == 'text')
        img_count = sum(1 for b in card.blocks if b.block_type == 'image')
        card.token_weight = 100.0 + (text_len * 0.8) + (img_count * 350.0)