import os
from copy import deepcopy
from core.state_context import SystemState, PosterCard
from agents.parser_agent import ParserAgent
from agents.summarizer_agent import SummarizerAgent
from agents.planner_agent import PlannerAgent
from agents.critic_agent import CriticAgent
from renderer.engine import RendererEngine
from core.constrained_layout import apply_constrained_layout
from utils.logger import system_logger

class AutoPosterPipeline:
    """
    The orchestrator managing the FSM, agentic interactions, and Checkpoint Rollbacks.
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
        
        system_logger.info("=== PHASE 2 & 3 & 4: PLANNING, RENDERING & REVIEW ===")
        
        # [ANTI-OSCILLATION UPGRADE]: Track the best state to prevent reverse optimization
        min_loss = float('inf')
        best_cards_snapshot = []
        
        while state.current_iteration < state.max_iterations:
            system_logger.info(f"--- Iteration {state.current_iteration + 1}/{state.max_iterations} ---")
            
            await self.planner.plan_layout(state)
            
            col_heights_dict = apply_constrained_layout(
                cards=state.cards, 
                canvas_width=self.renderer.viewport_width, 
                canvas_height=self.renderer.viewport_height
            )
            
            debug_img_path = await self.renderer.render_poster(state, is_debug=True)
            is_perfect = await self.critic.review_poster(state, debug_img_path)
            
            # --- Composite Loss Calculation ---
            # 1. Hard Constraint Penalty (Visual Issues)
            current_issues = len(state.latest_feedback.get("issues", [])) if state.latest_feedback else 0
            
            # 2. Soft Constraint Penalty (Aesthetic Variance)
            heights = list(col_heights_dict.values())
            if heights:
                mean_h = sum(heights) / len(heights)
                variance = sum((h - mean_h) ** 2 for h in heights) / len(heights)
            else:
                variance = 0
                
            # Total Loss = Issue Penalty (Massive) + Imbalance Penalty (Minor)
            # This ensures 0-issue layouts always beat 1-issue layouts, 
            # but among 0-issue layouts, the most visually balanced one wins.
            total_loss = (current_issues * 100000) + variance
            
            system_logger.info(f"Iteration Loss: {total_loss:.2f} (Issues: {current_issues}, Variance: {variance:.2f})")
            
            if total_loss < min_loss:
                min_loss = total_loss
                best_cards_snapshot = [card.model_copy(deep=True) for card in state.cards]
                system_logger.info(">>> New Best Checkpoint Saved!")
            
            if is_perfect and variance < 5000: # Threshold for "good enough" balance
                system_logger.info("Pipeline Converged! Layout is perfectly balanced.")
                break
                
            state.current_iteration += 1
            
        # --- Fallback & Rollback ---
        if not state.is_converged:
            system_logger.warning(f"Max iterations reached. Rolling back to best state (Issues: {min_loss}).")
            state.is_fallback_triggered = True
            
            # Rollback to the best snapshot
            if best_cards_snapshot:
                state.cards = best_cards_snapshot
                # Recalculate coordinates just to ensure the renderer gets perfectly synced data
                apply_constrained_layout(
                    cards=state.cards, 
                    canvas_width=self.renderer.viewport_width, 
                    canvas_height=self.renderer.viewport_height
                )

        # === FINAL PHASE ===
        system_logger.info("=== FINAL PHASE: RENDERING CLEAN POSTER ===")
        final_poster_path = await self.renderer.render_poster(state, is_debug=False)
        
        return final_poster_path