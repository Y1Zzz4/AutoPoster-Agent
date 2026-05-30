import os
from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright
from core.state_context import SystemState
from utils.logger import system_logger

class RendererEngine:
    """
    Headless Renderer mapping spatial properties and HTML to an image.
    """
    def __init__(self):
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template('poster_template.html')
        
        self.viewport_width = 1920
        self.viewport_height = 1080
        self.base_output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'outputs')

    async def render_poster(self, state: SystemState, is_debug: bool = False) -> str:
        # Pass state.cards instead of blocks
        html_content = self.template.render(
            cards=state.cards,
            is_debug=is_debug
        )
        
        target_dir = os.path.join(self.base_output_dir, state.document_name)
        os.makedirs(target_dir, exist_ok=True)
        
        file_suffix = "debug" if is_debug else "clean"
        output_filename = f"poster_{state.session_id}_iter{state.current_iteration}_{file_suffix}.png"
        output_filepath = os.path.join(target_dir, output_filename)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": self.viewport_width, "height": self.viewport_height},
                device_scale_factor=2 
            )
            await page.set_content(html_content, wait_until="networkidle")
            await page.screenshot(path=output_filepath, full_page=True)
            await browser.close()
            
        return output_filepath