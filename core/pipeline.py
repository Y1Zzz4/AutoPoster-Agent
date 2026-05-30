import os
import math
from core.state_context import SystemState
from agents.parser_agent import ParserAgent
from agents.summarizer_agent import SummarizerAgent
from agents.planner_agent import PlannerAgent
from agents.critic_agent import CriticAgent
from renderer.engine import RendererEngine
from core.constrained_layout import apply_constrained_layout
from utils.logger import system_logger

class AutoPosterPipeline:
    """
    Orchestrates the Multi-Agent pipeline, managing FSM transitions, aesthetic loss functions, 
    and dynamic semantic recovery.
    """
    def __init__(self):
        self.parser = ParserAgent()
        self.summarizer = SummarizerAgent()
        self.planner = PlannerAgent()
        self.renderer = RendererEngine()
        self.critic = CriticAgent()
        system_logger.info("AutoPoster Pipeline initialized.")

    async def run(self, input_filepath: str) -> str:
        doc_name = os.path.splitext(os.path.basename(input_filepath))[0]
        state = SystemState(
            original_document_path=input_filepath,
            document_name=doc_name
        )
        
        system_logger.info("=== PHASE 1: PARSING DOCUMENT ===")
        state.cards = self.parser.parse_markdown(input_filepath)
        
        system_logger.info("=== PHASE 1.5: SUMMARIZING LONG TEXTS ===")
        await self.summarizer.execute_summary(state)
        
        system_logger.info("=== PHASE 2, 3 & 4: PLANNING, RENDERING & REVIEW ===")
        
        min_loss = float('inf')
        best_cards_snapshot = []
        state.is_converged = False 
        
        while state.current_iteration < state.max_iterations:
            system_logger.info(f"--- Iteration {state.current_iteration + 1}/{state.max_iterations} ---")
            
            await self.planner.plan_layout(state)
            
            col_heights_dict = apply_constrained_layout(
                cards=state.cards, 
                canvas_width=self.renderer.viewport_width, 
                canvas_height=self.renderer.viewport_height
            )
            
            debug_img_path = await self.renderer.render_poster(state, is_debug=True)
            is_perfect = await self.critic.evaluate_layout(state, debug_img_path)
            
            # --- Aesthetic & Structural Loss Calculation ---
            current_issues = len(state.latest_feedback.get("issues", [])) if state.latest_feedback else 0
            heights = list(col_heights_dict.values())
            variance = sum((h - sum(heights)/len(heights))**2 for h in heights) / len(heights) if heights else 0
            total_loss = (current_issues * 100000) + variance
            
            if total_loss < min_loss:
                min_loss = total_loss
                best_cards_snapshot = [card.model_copy(deep=True) for card in state.cards]
                system_logger.info(f"Checkpoint Saved: Best state updated (Loss: {total_loss:.2f})")
            
            if is_perfect:
                state.is_converged = True 
                break
                
            # --- Dynamic Semantic Compression Hook ---
            issues = state.latest_feedback.get("issues", []) if state.latest_feedback else []
            has_overflow = any("overflow" in i.get("description", "").lower() or "clip" in i.get("description", "").lower() for i in issues)
            
            if has_overflow:
                system_logger.info("Overflow detected. Triggering semantic compression on specific cards.")
                compressed_ids = await self.summarizer.compress_overflow_card(state)
                
                # Resynchronize physical weight only for the modified cards
                if compressed_ids:
                    for card in state.cards:
                        if card.card_id in compressed_ids:
                            self.summarizer._recalculate_card_weight(card)
                            
            state.current_iteration += 1
            
        # --- CONCLUSION LOGIC ---
        if state.is_converged:
            system_logger.info("Pipeline Converged: Layout finalized successfully without critical issues.")
        else:
            system_logger.warning(f"Max iterations reached. Rolling back to best iteration (Best Loss: {min_loss:.2f}).")
            state.is_fallback_triggered = True
            if best_cards_snapshot:
                state.cards = best_cards_snapshot
                apply_constrained_layout(state.cards, self.renderer.viewport_width, self.renderer.viewport_height)

        system_logger.info("=== FINAL PHASE: RENDERING CLEAN POSTER ===")
        return await self.renderer.render_poster(state, is_debug=False)