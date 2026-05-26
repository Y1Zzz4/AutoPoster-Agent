import os
from core.state_context import SystemState
from agents.parser_agent import ParserAgent
from agents.planner_agent import PlannerAgent
from agents.critic_agent import CriticAgent
from renderer.engine import RendererEngine
from core.bsp_algorithm import apply_bsp_layout
from utils.logger import system_logger

class AutoPosterPipeline:
    """
    The orchestrator of the entire Multi-Agent workflow.
    It manages the State Machine and the feedback loop.
    """
    def __init__(self):
        self.parser = ParserAgent()
        self.planner = PlannerAgent()
        self.renderer = RendererEngine()
        self.critic = CriticAgent()
        system_logger.info("AutoPoster Pipeline initialized with all Agents.")

    async def run(self, input_filepath: str) -> str:
        """
        Executes the main pipeline.
        
        Args:
            input_filepath: The path to the source markdown/pdf file.
            
        Returns:
            The path to the final rendered poster.
        """
        # 1. Initialize the global state machine
        doc_name = os.path.splitext(os.path.basename(input_filepath))[0]
        state = SystemState(
            original_document_path=input_filepath,
            document_name=doc_name
        )
        
        # 2. Phase 1: Data Ingestion (Parse Document once)
        system_logger.info("=== PHASE 1: PARSING DOCUMENT ===")
        state.content_blocks = self.parser.parse_markdown(input_filepath)
        
        # 3. The Grand Closed-Loop (Feedback Loop)
        system_logger.info("=== PHASE 2 & 3 & 4: PLANNING, RENDERING & REVIEW ===")
        
        while state.current_iteration < state.max_iterations:
            system_logger.info(f"--- Starting Iteration {state.current_iteration + 1}/{state.max_iterations} ---")
            
            # Step A: LLM plans the semantic layout and applies weights
            await self.planner.plan_layout(state)
            
            # Step B: Mathematical algorithm calculates exact pixel coordinates
            apply_bsp_layout(
                blocks=state.content_blocks, 
                canvas_width=self.renderer.viewport_width, 
                canvas_height=self.renderer.viewport_height
            )
            
            # Step C: Render the DEBUG version of the poster for the Critic
            debug_img_path = await self.renderer.render_poster(state, is_debug=True)
            
            # Step D: Critic evaluates the debug poster
            is_perfect = await self.critic.review_poster(state, debug_img_path)
            
            if is_perfect:
                system_logger.info("Pipeline Converged! Layout is optimal.")
                break
                
            # If not perfect, increment iteration and loop again
            state.current_iteration += 1
            
        # 4. Fallback / Finalization
        if not state.is_converged:
            system_logger.warning("Max iterations reached without perfect convergence. Applying graceful fallback.")
            state.is_fallback_triggered = True

        # 5. Final Render: Generate the CLEAN poster without red borders
        system_logger.info("=== FINAL PHASE: RENDERING CLEAN POSTER ===")
        final_poster_path = await self.renderer.render_poster(state, is_debug=False)
        
        system_logger.info(f"Task Complete! Final poster saved at: {final_poster_path}")
        return final_poster_path