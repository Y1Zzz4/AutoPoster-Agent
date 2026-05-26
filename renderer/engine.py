import os
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from core.state_context import SystemState
from utils.logger import system_logger

class RendererEngine:
    """
    The Headless Renderer Engine.
    Uses Jinja2 to inject data into HTML and Playwright to render and screenshot the layout.
    """
    def __init__(self):
        # Set up Jinja2 environment to load templates from the current directory's 'templates' folder
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template('poster_template.html')
        
        # Standard poster resolution (e.g., Vertical HD)
        self.viewport_width = 1080
        self.viewport_height = 1920
        
        # Ensure output directory exists
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        system_logger.info("RendererEngine initialized.")

    async def render_poster(self, state: SystemState, is_debug: bool = False) -> str:
        """
        Renders the current state into an image.
        
        Args:
            state (SystemState): The global state containing blocks with coordinates.
            is_debug (bool): If True, renders the diagnostic version (red borders & IDs) for the Critic.
            
        Returns:
            str: The absolute path to the generated image file.
        """
        # 1. Generate HTML string via Jinja2
        html_content = self.template.render(
            blocks=state.content_blocks,
            is_debug=is_debug
        )
        
        file_suffix = "debug" if is_debug else "clean"
        output_filename = f"poster_{state.session_id}_iter{state.current_iteration}_{file_suffix}.png"
        output_filepath = os.path.join(self.output_dir, output_filename)
        
        system_logger.info(f"Launching Playwright to render {file_suffix} poster...")
        
        # 2. Launch headless browser
        async with async_playwright() as p:
            # We use Chromium for accurate CSS rendering
            browser = await p.chromium.launch(headless=True)
            
            # Set the exact viewport size matching our poster dimensions
            page = await browser.new_page(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                device_scale_factor=2 # 2x scaling for high-resolution output (Retina quality)
            )
            
            # 3. Inject the generated HTML and wait for network/fonts to settle
            await page.set_content(html_content, wait_until="networkidle")
            
            # 4. Take a full-page screenshot
            await page.screenshot(path=output_filepath, full_page=True)
            
            await browser.close()
            
        system_logger.info(f"Successfully saved rendered image to: {output_filepath}")
        return output_filepath