import os
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
    The orchestrator managing the FSM and agentic interactions.
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
        # Output is now List[PosterCard]
        state.cards = self.parser.parse_markdown(input_filepath)
        
        system_logger.info("=== PHASE 1.5: SUMMARIZING LONG TEXTS ===")
        await self.summarizer.execute_summary(state)
        
        system_logger.info("=== PHASE 2 & 3 & 4: PLANNING, RENDERING & REVIEW ===")
        
        while state.current_iteration < state.max_iterations:
            system_logger.info(f"--- Iteration {state.current_iteration + 1}/{state.max_iterations} ---")
            
            await self.planner.plan_layout(state)
            
            # Use Greedy Masonry algorithm on Cards
            apply_constrained_layout(
                cards=state.cards, 
                canvas_width=self.renderer.viewport_width, 
                canvas_height=self.renderer.viewport_height
            )
            
            debug_img_path = await self.renderer.render_poster(state, is_debug=True)
            is_perfect = await self.critic.review_poster(state, debug_img_path)
            
            if is_perfect:
                system_logger.info("Pipeline Converged! Layout is optimal.")
                break
                
            state.current_iteration += 1
            
        if not state.is_converged:
            system_logger.warning("Max iterations reached. Applying graceful fallback.")
            state.is_fallback_triggered = True

        system_logger.info("=== FINAL PHASE: RENDERING CLEAN POSTER ===")
        final_poster_path = await self.renderer.render_poster(state, is_debug=False)
        
        return final_poster_path