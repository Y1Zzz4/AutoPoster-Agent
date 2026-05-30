import os
from core.state_context import SystemState
from agents.preprocessor_agent import PreprocessorAgent
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
        self.preprocessor = PreprocessorAgent()
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
        
        system_logger.info("=== PHASE 0: GLOBAL PRE-COMPRESSION ===")
        processed_filepath = await self.preprocessor.compress_document(input_filepath)

        system_logger.info("=== PHASE 1: PARSING DOCUMENT ===")
        state.cards = await self.parser.parse_markdown(processed_filepath)
        
        system_logger.info("=== PHASE 1.5: SUMMARIZING LONG TEXTS ===")
        await self.summarizer.execute_summary(state)
        
        system_logger.info("=== PHASE 2, 3 & 4: PLANNING, RENDERING & REVIEW ===")
        
        min_loss = float('inf')
        best_cards_snapshot = []
        state.is_converged = False 

        previous_loss = float('inf')
        patience_counter = 0
        PATIENCE_LIMIT = 2
        
        while state.current_iteration < state.max_iterations:
            iteration_id = state.current_iteration + 1
            system_logger.info(f"\n========== ITERATION {iteration_id}/{state.max_iterations} ==========")
            
            system_logger.info("[Step 1] PlannerAgent calculating spatial weights...")
            await self.planner.plan_layout(state)
            
            # Instantaneous local discrete matrix evaluation
            system_logger.info("[Step 2] Executing internal Rigid-Flex Cartesian Engine...")
            while True:
                layout_metrics = apply_constrained_layout(
                    cards=state.cards, 
                    canvas_width=self.renderer.viewport_width, 
                    canvas_height=self.renderer.viewport_height
                )
                
                is_math_overflow = layout_metrics.get("is_overflowing", False)
                overflow_cards = layout_metrics.get("overflow_cards", [])
                
                if is_math_overflow and overflow_cards:
                    lod_downgraded = False
                    for cid in overflow_cards:
                        target_card = next((c for c in state.cards if c.card_id == cid), None)
                        # Step down the discrete gradient until Tier 3 (25%) limit
                        if target_card and target_card.current_lod < 3:
                            target_card.current_lod += 1
                            self.summarizer._apply_lod_to_blocks(target_card)
                            lod_downgraded = True
                            system_logger.warning(f"Spatial overflow inside card {cid}. Stepping down to LOD Tier {target_card.current_lod}.")
                    
                    if lod_downgraded:
                        # Re-calculate packing metrics instantly without billing LLM/VLM tokens
                        continue 
                    else:
                        system_logger.error("All conflicting regions reached minimum structural bounds (LOD Tier 3).")
                        break
                else:
                    break # Visual boundary equilibrium established in memory
            
            # --- Normal VLM Aesthetic Review ---
            system_logger.info("[Step 3] Rendering headless layout for VLM Review...")
            debug_img_path = await self.renderer.render_poster(state, is_debug=True)
            is_perfect = await self.critic.evaluate_layout(state, debug_img_path)
            
            current_issues = len(state.latest_feedback.get("issues", [])) if state.latest_feedback else 0
            col_heights_dict = layout_metrics.get("heights", {})
            heights = list(col_heights_dict.values())
            variance = sum((h - sum(heights)/len(heights))**2 for h in heights) / len(heights) if heights else 0

            total_loss = (current_issues * 100000) + variance
            system_logger.info(f"[Step 4] Current Layout Loss evaluated at: {total_loss:.2f}")

            if total_loss < min_loss:
                min_loss = total_loss
                best_cards_snapshot = [card.model_copy(deep=True) for card in state.cards]
                system_logger.info("Checkpoint updated with new minimum loss.")
            
            loss_diff = abs(previous_loss - total_loss)
            if loss_diff < 1.0:
                patience_counter += 1
                system_logger.info(f"  -> [Early Stopping] Loss stabilized. Patience: {patience_counter}/{PATIENCE_LIMIT}")
            else:
                patience_counter = 0
                
            previous_loss = total_loss
            
            if is_perfect or patience_counter >= PATIENCE_LIMIT:
                state.is_converged = True 
                if not is_perfect:
                    system_logger.info("  -> [Early Stopping] Triggered: Spatial geometry has converged. No further optimization is physically possible.")
                break
                            
            state.current_iteration += 1
            system_logger.info(f"=========================================\n")
            
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